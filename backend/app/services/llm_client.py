from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json
import logging
import re
import sys
import traceback
from typing import Any, Callable, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger("llm_client")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [LLM_CLIENT] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

try:
    import google.generativeai as genai
except ImportError:
    genai = None

_RESOLVED_GEMINI_MODEL: Optional[str] = None


@dataclass
class LLMResponse:
    reply: str
    action_taken: Optional[str] = None
    executed_actions: List[str] = field(default_factory=list)
    raw_response: Optional[Any] = None


class LLMClient(ABC):
    @abstractmethod
    def generate(
        self,
        system_instruction: str,
        user_message: str,
        tools: List[Callable],
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
        tool_executors: Optional[Dict[str, Callable]] = None,
    ) -> LLMResponse:
        pass


class GeminiClient(LLMClient):
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL

    def _resolve_model(self) -> str:
        global _RESOLVED_GEMINI_MODEL
        if _RESOLVED_GEMINI_MODEL:
            return _RESOLVED_GEMINI_MODEL

        configured = self.model_name or "gemini-1.5-flash"
        if not self.api_key or genai is None:
            return configured

        try:
            genai.configure(api_key=self.api_key)
            models = list(genai.list_models())
            supported_names = [
                m.name.replace("models/", "")
                for m in models
                if "generateContent" in getattr(m, "supported_generation_methods", [])
            ]
            if configured in supported_names:
                _RESOLVED_GEMINI_MODEL = configured
                return _RESOLVED_GEMINI_MODEL
            for fallback in ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.0-pro"]:
                if fallback in supported_names:
                    _RESOLVED_GEMINI_MODEL = fallback
                    return _RESOLVED_GEMINI_MODEL
            if supported_names:
                _RESOLVED_GEMINI_MODEL = supported_names[0]
                return _RESOLVED_GEMINI_MODEL
        except Exception as e:
            logger.warning(f"Failed to list Gemini models: {e}. Defaulting to '{configured}'")

        _RESOLVED_GEMINI_MODEL = configured
        return _RESOLVED_GEMINI_MODEL

    def generate(
        self,
        system_instruction: str,
        user_message: str,
        tools: List[Callable],
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
        tool_executors: Optional[Dict[str, Callable]] = None,
    ) -> LLMResponse:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        if genai is None:
            raise ImportError("google.generativeai module is not installed.")

        active_model = self._resolve_model()
        logger.info(f"[GEMINI] Calling model: {active_model}")

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(
            model_name=active_model,
            tools=tools,
            system_instruction=system_instruction,
        )

        chat = model.start_chat(enable_automatic_function_calling=True)
        response = chat.send_message(user_message)
        reply_text = response.text if hasattr(response, "text") and response.text else "I've processed your request."

        return LLMResponse(
            reply=reply_text,
            raw_response=response,
        )


class OllamaClient(LLMClient):
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.timeout = timeout

    def generate(
        self,
        system_instruction: str,
        user_message: str,
        tools: List[Callable],
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
        tool_executors: Optional[Dict[str, Callable]] = None,
    ) -> LLMResponse:
        logger.info(f"[OLLAMA] Calling Ollama at {self.base_url}/v1/chat/completions (Model: {self.model})")

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_message},
        ]

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }

        if tool_schemas:
            payload["tools"] = tool_schemas

        executed_actions: List[str] = []

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/v1/chat/completions", json=payload)
            if resp.status_code != 200:
                logger.error(f"[OLLAMA] Error response {resp.status_code}: {resp.text}")
                raise RuntimeError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")

            data = resp.json()
            choice = data.get("choices", [{}])[0]
            message_obj = choice.get("message", {})

            tool_calls = message_obj.get("tool_calls", [])
            if tool_calls and tool_executors:
                logger.info(f"[OLLAMA] Model requested {len(tool_calls)} tool calls: {tool_calls}")
                messages.append(message_obj)

                for tc in tool_calls:
                    func_info = tc.get("function", {})
                    fn_name = func_info.get("name", "")
                    fn_args_raw = func_info.get("arguments", "{}")

                    if isinstance(fn_args_raw, str):
                        try:
                            fn_args = json.loads(fn_args_raw)
                        except Exception:
                            fn_args = {}
                    else:
                        fn_args = fn_args_raw or {}

                    executed_actions.append(fn_name)
                    if fn_name in tool_executors:
                        logger.info(f"[OLLAMA] Executing tool '{fn_name}' with args {fn_args}")
                        try:
                            tool_result = tool_executors[fn_name](**fn_args)
                        except Exception as e:
                            logger.error(f"Error executing tool {fn_name}: {e}")
                            tool_result = {"status": "error", "message": str(e)}
                    else:
                        tool_result = {"status": "error", "message": f"Tool '{fn_name}' not recognized."}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", f"call_{fn_name}"),
                        "name": fn_name,
                        "content": json.dumps(tool_result),
                    })

                followup_payload = {
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                }
                followup_resp = client.post(f"{self.base_url}/v1/chat/completions", json=followup_payload)
                if followup_resp.status_code == 200:
                    followup_data = followup_resp.json()
                    final_choice = followup_data.get("choices", [{}])[0]
                    reply_text = final_choice.get("message", {}).get("content", "")
                else:
                    reply_text = "I've completed the scheduled actions."
            else:
                reply_text = message_obj.get("content", "") or "I've processed your request."

        return LLMResponse(
            reply=reply_text,
            executed_actions=executed_actions,
            raw_response=data,
        )


def get_llm_client() -> LLMClient:
    provider = (settings.LLM_PROVIDER or "ollama").strip().lower()
    if provider == "gemini":
        return GeminiClient()
    elif provider == "ollama":
        return OllamaClient()
    else:
        logger.warning(f"Unknown LLM_PROVIDER '{provider}'. Defaulting to OllamaClient.")
        return OllamaClient()
