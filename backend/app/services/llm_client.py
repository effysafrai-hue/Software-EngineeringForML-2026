from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json
import logging
import sys
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

        configured = self.model_name
        if not configured or configured == "gemini-3.6-flash":
            configured = "gemini-1.5-flash"

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
            for fallback in ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-1.0-pro"]:
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

        executed_actions: List[str] = []
        try:
            for message in getattr(chat, "history", []):
                for part in getattr(message, "parts", []):
                    fn_call = getattr(part, "function_call", None)
                    if fn_call and getattr(fn_call, "name", None):
                        executed_actions.append(fn_call.name)
        except Exception:
            pass

        return LLMResponse(
            reply=reply_text,
            executed_actions=executed_actions,
            raw_response=response,
        )


def _extract_message(data: Dict[str, Any]) -> tuple:
    """Return (content, tool_calls) from an Ollama chat response.

    The native /api/chat endpoint answers with a single "message" object; the
    OpenAI-compatible route (and any proxy in front of it) wraps the same object
    in "choices". Both shapes are accepted so the client keeps working whichever
    endpoint OLLAMA_BASE_URL points at.
    """
    message_obj = data.get("message")
    if not isinstance(message_obj, dict):
        choices = data.get("choices") or []
        message_obj = choices[0].get("message", {}) if choices else {}

    content = (message_obj.get("content") or "").strip()
    tool_calls = message_obj.get("tool_calls") or []
    return content, tool_calls


def _parse_tool_args(raw: Any) -> Dict[str, Any]:
    """Normalise tool arguments, which arrive as a dict natively and as a JSON string over the OpenAI route."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"[OLLAMA] Could not parse tool arguments: {raw!r}")
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


class OllamaClient(LLMClient):
    """Ollama chat client with multi-turn tool calling.

    Talks to the native /api/chat endpoint because, unlike the OpenAI-compatible
    route, it accepts per-request `options`. num_ctx matters most: the agent
    prompt (scheduling rules + retrieved course grounding + tool schemas) runs
    past Ollama's 4096-token server default, and an over-long prompt is silently
    truncated, which drops the tool definitions and the reference date the model
    needs. Sampling is greedy so date arithmetic and tool arguments are stable
    across runs.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        num_ctx: Optional[int] = None,
        temperature: Optional[float] = None,
        max_tool_turns: Optional[int] = None,
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        self.timeout = float(timeout if timeout is not None else settings.OLLAMA_TIMEOUT)
        self.num_ctx = int(num_ctx if num_ctx is not None else settings.OLLAMA_NUM_CTX)
        self.temperature = float(temperature if temperature is not None else settings.OLLAMA_TEMPERATURE)
        self.max_tool_turns = int(max_tool_turns if max_tool_turns is not None else settings.OLLAMA_MAX_TOOL_TURNS)

    def _chat(
        self,
        client: httpx.Client,
        messages: List[Dict[str, Any]],
        tool_schemas: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": settings.OLLAMA_KEEP_ALIVE,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
                "num_predict": settings.OLLAMA_NUM_PREDICT,
                "seed": 0,
            },
        }
        if tool_schemas:
            payload["tools"] = tool_schemas

        try:
            resp = client.post(f"{self.base_url}/api/chat", json=payload)
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"Could not reach the Ollama server at {self.base_url} ({type(exc).__name__}: {exc})."
            ) from exc

        if resp.status_code != 200:
            logger.error(f"[OLLAMA] Error response {resp.status_code}: {resp.text}")
            if resp.status_code == 404:
                raise RuntimeError(
                    f"Ollama at {self.base_url} does not have the model '{self.model}'. "
                    f"Pull it first: `ollama pull {self.model}`. Server said: {resp.text.strip()}"
                )
            raise RuntimeError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")
        return resp.json()

    def generate(
        self,
        system_instruction: str,
        user_message: str,
        tools: List[Callable],
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
        tool_executors: Optional[Dict[str, Callable]] = None,
    ) -> LLMResponse:
        logger.info(
            f"[OLLAMA] Calling {self.base_url}/api/chat (model={self.model}, "
            f"num_ctx={self.num_ctx}, temperature={self.temperature})"
        )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_message},
        ]
        offer_tools = tool_schemas if tool_executors else None

        executed_actions: List[str] = []
        # Small models loop: after a tool result they often re-issue the very same
        # call instead of answering. Replaying the stored result keeps that from
        # duplicating a calendar write.
        results_by_call: Dict[str, str] = {}
        reply_text = ""
        last_data: Optional[Dict[str, Any]] = None

        with httpx.Client(timeout=self.timeout) as client:
            for turn in range(1, self.max_tool_turns + 1):
                last_data = self._chat(client, messages, offer_tools)
                content, tool_calls = _extract_message(last_data)

                if not tool_calls:
                    reply_text = content
                    break

                logger.info(f"[OLLAMA] (Turn {turn}) Model requested {len(tool_calls)} tool call(s): {tool_calls}")
                messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

                for tc in tool_calls:
                    func_info = tc.get("function", {})
                    fn_name = func_info.get("name", "")
                    fn_args = _parse_tool_args(func_info.get("arguments"))
                    signature = f"{fn_name}:{json.dumps(fn_args, sort_keys=True, default=str)}"

                    if signature in results_by_call:
                        logger.info(f"[OLLAMA] Tool '{fn_name}' already called with these arguments; replaying result")
                        tool_content = results_by_call[signature]
                    else:
                        if fn_name in tool_executors:
                            logger.info(f"[OLLAMA] Executing tool '{fn_name}' with args {fn_args}")
                            executed_actions.append(fn_name)
                            try:
                                tool_result = tool_executors[fn_name](**fn_args)
                            except Exception as e:
                                logger.error(f"Error executing tool {fn_name}: {e}")
                                tool_result = {"status": "error", "message": str(e)}
                        else:
                            logger.warning(f"[OLLAMA] Model called unknown tool '{fn_name}'")
                            tool_result = {"status": "error", "message": f"Tool '{fn_name}' not recognized."}
                        tool_content = json.dumps(tool_result, default=str)
                        results_by_call[signature] = tool_content

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id") or f"call_{fn_name}_{turn}",
                        "name": fn_name,
                        "content": tool_content,
                    })

            if not reply_text and offer_tools:
                # Either the turn budget went entirely to tool calls, or the model
                # answered with nothing at all. Ask once more with the tools
                # withheld, so it has to put what it did into words.
                logger.info("[OLLAMA] No reply text yet; requesting a final answer without tools")
                last_data = self._chat(client, messages, None)
                reply_text, _ = _extract_message(last_data)

        if not reply_text:
            raise RuntimeError(
                f"Ollama model '{self.model}' returned an empty reply after {len(executed_actions)} tool call(s)."
            )

        return LLMResponse(
            reply=reply_text,
            executed_actions=executed_actions,
            raw_response=last_data,
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
