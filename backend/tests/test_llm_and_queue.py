import asyncio
from types import SimpleNamespace
import pytest
from unittest.mock import MagicMock, patch

from app.services.chat_queue import ChatQueueManager, Priority, ChatJob
from app.services.llm_client import GeminiClient, OllamaClient, LLMResponse, get_llm_client


@pytest.mark.asyncio
async def test_priority_queue_ordering():
    """Test that higher priority jobs are processed ahead of lower priority jobs."""
    queue = ChatQueueManager(max_workers=1)
    await queue.start()

    execution_order = []

    def hold_worker():
        import time
        time.sleep(0.05)
        execution_order.append("holding")
        return "hold"

    def task(name):
        execution_order.append(name)
        return name

    # Submit holding task (takes the 1 worker) and yield to event loop so worker picks it up
    t_hold = asyncio.create_task(queue.submit(Priority.BACKGROUND_SUMMARY, hold_worker))
    await asyncio.sleep(0.01)

    # Now that the single worker is occupied, submit low priority (3), then high priority (1)
    t_bg = asyncio.create_task(queue.submit(Priority.BACKGROUND_SUMMARY, task, "background"))
    t_inter = asyncio.create_task(queue.submit(Priority.INTERACTIVE_CHAT, task, "interactive"))

    await asyncio.gather(t_hold, t_bg, t_inter)
    await queue.stop()

    assert execution_order == ["holding", "interactive", "background"]


@pytest.mark.asyncio
async def test_priority_queue_unstarted_sync_fallback():
    """When worker pool is not started (e.g. test environments), submit works synchronously in thread."""
    queue = ChatQueueManager(max_workers=2)

    def add(a, b):
        return a + b

    result = await queue.submit(Priority.INTERACTIVE_CHAT, add, 10, 20)
    assert result == 30


def test_ollama_client_mock_completion():
    """Test that OllamaClient handles standard text completion responses."""
    client = OllamaClient(base_url="http://mock-ollama:11434", model="llama3.1:8b")

    mock_resp_data = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Hello! I can help you with your calendar.",
                }
            }
        ]
    }

    with patch("httpx.Client.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_resp_data
        mock_post.return_value = mock_response

        res = client.generate(
            system_instruction="System instructions",
            user_message="Hello",
            tools=[],
        )

        assert res.reply == "Hello! I can help you with your calendar."
        assert res.executed_actions == []


def test_ollama_client_mock_tool_calling():
    """Test that OllamaClient executes tool calls and makes follow-up request."""
    client = OllamaClient(base_url="http://mock-ollama:11434", model="llama3.1:8b")

    first_resp_data = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_123",
                            "type": "function",
                            "function": {
                                "name": "create_event",
                                "arguments": '{"title": "Study Group", "start_time": "2026-06-17T17:00:00Z", "end_time": "2026-06-17T18:00:00Z"}',
                            },
                        }
                    ],
                }
            }
        ]
    }

    second_resp_data = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "I have scheduled the Study Group event for you.",
                }
            }
        ]
    }

    executed = []

    def mock_create_event(**kw):
        executed.append(kw.get("title"))
        return {"status": "success", "id": 42}

    with patch("httpx.Client.post") as mock_post:
        mock_resp1 = MagicMock()
        mock_resp1.status_code = 200
        mock_resp1.json.return_value = first_resp_data

        mock_resp2 = MagicMock()
        mock_resp2.status_code = 200
        mock_resp2.json.return_value = second_resp_data

        mock_post.side_effect = [mock_resp1, mock_resp2]

        res = client.generate(
            system_instruction="System prompt",
            user_message="Schedule study group",
            tools=[],
            tool_schemas=[{"type": "function", "function": {"name": "create_event"}}],
            tool_executors={"create_event": mock_create_event},
        )

        assert executed == ["Study Group"]
        assert res.reply == "I have scheduled the Study Group event for you."
        assert res.executed_actions == ["create_event"]


def _mock_response(payload):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = payload
    return resp


def _native_text(content):
    return {"message": {"role": "assistant", "content": content}}


def _native_tool_call(name, arguments):
    return {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": name, "arguments": arguments}}],
        }
    }


def test_ollama_client_reads_native_api_chat_shape():
    """The native /api/chat endpoint returns a single `message`, not `choices`."""
    client = OllamaClient(base_url="http://mock-ollama:11434", model="llama3.1:8b")

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = _mock_response(_native_text("You have nothing scheduled tomorrow."))

        res = client.generate(
            system_instruction="System instructions",
            user_message="Anything tomorrow?",
            tools=[],
        )

    assert res.reply == "You have nothing scheduled tomorrow."
    assert res.executed_actions == []

    # Sampling must be pinned, and the context window set explicitly: the default
    # server context truncates the agent prompt and drops the tool definitions.
    payload = mock_post.call_args_list[0].kwargs["json"]
    assert payload["options"]["temperature"] == 0.0
    assert payload["options"]["num_ctx"] >= 8192
    assert payload["stream"] is False


def test_ollama_client_does_not_repeat_an_identical_tool_call():
    """A model that re-issues the same call must not write the event twice."""
    client = OllamaClient(base_url="http://mock-ollama:11434", model="llama3.1:8b")

    args = {"title": "Study Group", "start_time": "2026-06-17T17:00:00Z", "end_time": "2026-06-17T18:00:00Z"}
    calls = []

    def mock_create_event(**kw):
        calls.append(kw)
        return {"status": "success", "id": 42}

    with patch("httpx.Client.post") as mock_post:
        mock_post.side_effect = [
            _mock_response(_native_tool_call("create_event", args)),
            _mock_response(_native_tool_call("create_event", dict(args))),
            _mock_response(_native_text("Scheduled the Study Group.")),
        ]

        res = client.generate(
            system_instruction="System prompt",
            user_message="Schedule study group",
            tools=[],
            tool_schemas=[{"type": "function", "function": {"name": "create_event"}}],
            tool_executors={"create_event": mock_create_event},
        )

    assert len(calls) == 1
    assert res.executed_actions == ["create_event"]
    assert res.reply == "Scheduled the Study Group."


def test_ollama_client_forces_a_final_answer_when_tool_turns_run_out():
    """When the turn budget goes to tool calls, ask again with the tools withheld."""
    client = OllamaClient(base_url="http://mock-ollama:11434", model="llama3.1:8b", max_tool_turns=2)

    with patch("httpx.Client.post") as mock_post:
        mock_post.side_effect = [
            _mock_response(_native_tool_call("list_events", {"search_query": "Dr. Smith"})),
            _mock_response(_native_tool_call("update_event", {"event_id": 7, "start_time": "2026-06-15T11:00:00Z"})),
            _mock_response(_native_text("Moved the Dr. Smith consultation to Monday at 11:00.")),
        ]

        res = client.generate(
            system_instruction="System prompt",
            user_message="Reschedule the Dr. Smith consultation to Monday at 11am",
            tools=[],
            tool_schemas=[{"type": "function", "function": {"name": "list_events"}}],
            tool_executors={
                "list_events": lambda **kw: {"status": "success", "events": [{"id": 7, "title": "Dr. Smith consultation"}]},
                "update_event": lambda **kw: {"status": "success", "id": 7},
            },
        )

    assert res.executed_actions == ["list_events", "update_event"]
    assert res.reply == "Moved the Dr. Smith consultation to Monday at 11:00."
    assert mock_post.call_count == 3
    assert "tools" not in mock_post.call_args_list[2].kwargs["json"]


def test_ollama_client_reports_missing_model():
    """A model that was never pulled must surface as a clear error, not an empty reply."""
    client = OllamaClient(base_url="http://mock-ollama:11434", model="llama3.1:8b")

    with patch("httpx.Client.post") as mock_post:
        resp = MagicMock()
        resp.status_code = 404
        resp.text = '{"error":"model \'llama3.1:8b\' not found"}'
        mock_post.return_value = resp

        with pytest.raises(RuntimeError, match="does not have the model"):
            client.generate(system_instruction="s", user_message="hi", tools=[])


# ---------------------------------------------------------------------------
# Gemini model resolution.
#
# Google retires models, and a retired one is still returned by list_models() —
# it only fails at generate time. The detection below is string matching against
# two different SDK transports, so it is worth pinning.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_gemini_model_cache():
    """The resolved name and the rejection set are process-wide globals."""
    from app.services import llm_client as mod

    mod._RESOLVED_GEMINI_MODEL = None
    mod._REJECTED_GEMINI_MODELS.clear()
    yield
    mod._RESOLVED_GEMINI_MODEL = None
    mod._REJECTED_GEMINI_MODELS.clear()


@pytest.mark.parametrize(
    "message",
    [
        # grpc transport, which is what the google-generativeai SDK raises here.
        'status = StatusCode.NOT_FOUND details = "This model models/gemini-2.5-flash is no '
        'longer available to new users. Please update your code to use models/gemini-3.6-flash"',
        # REST transport.
        "404 models/gemini-1.5-flash is not found for API version v1beta, "
        "or is not supported for generateContent.",
    ],
)
def test_a_retired_model_error_is_recognised(message):
    from app.services.llm_client import _is_model_not_found

    assert _is_model_not_found(Exception(message)) is True


@pytest.mark.parametrize(
    "message",
    [
        "429 Resource has been exhausted (e.g. check quota).",
        "403 Permission denied on resource project.",
        "500 Internal error encountered.",
        "Deadline exceeded",
    ],
)
def test_other_errors_are_not_mistaken_for_a_retired_model(message):
    """Misreading a quota error as a dead model would silently downgrade the model."""
    from app.services.llm_client import _is_model_not_found

    assert _is_model_not_found(Exception(message)) is False


def _listed_model(name):
    """A stand-in for a genai model entry.

    SimpleNamespace rather than MagicMock on purpose: MagicMock treats `name` as
    a constructor keyword for the mock itself, so `MagicMock(name="models/x").name`
    is not "models/x" and the assertion would pass for the wrong reason.
    """
    return SimpleNamespace(name=name, supported_generation_methods=["generateContent"])


def test_resolution_prefers_the_configured_model_when_the_key_can_reach_it():
    from app.services.llm_client import GeminiClient

    client = GeminiClient(api_key="test-key", model_name="gemini-3.6-flash")
    with patch("app.services.llm_client.genai") as fake_genai:
        fake_genai.list_models.return_value = [
            _listed_model("models/gemini-3.6-flash"),
            _listed_model("models/gemini-2.0-flash"),
        ]
        assert client._resolve_model() == "gemini-3.6-flash"


def test_resolution_falls_back_when_the_configured_model_is_not_listed():
    from app.services.llm_client import GeminiClient

    client = GeminiClient(api_key="test-key", model_name="gemini-9.9-imaginary")
    with patch("app.services.llm_client.genai") as fake_genai:
        fake_genai.list_models.return_value = [_listed_model("models/gemini-2.0-flash")]
        assert client._resolve_model() == "gemini-2.0-flash"


def test_resolution_skips_a_model_already_rejected_by_the_api():
    """After a NOT_FOUND the dead id must not be handed back again."""
    from app.services import llm_client as mod

    mod._REJECTED_GEMINI_MODELS.add("gemini-2.5-flash")
    client = mod.GeminiClient(api_key="test-key", model_name="gemini-2.5-flash")

    with patch("app.services.llm_client.genai") as fake_genai:
        fake_genai.list_models.return_value = [
            _listed_model("models/gemini-2.5-flash"),
            _listed_model("models/gemini-3.6-flash"),
        ]
        assert client._resolve_model() == "gemini-3.6-flash"


def test_resolution_still_makes_progress_when_listing_fails():
    """A rejected model plus an unreachable list_models must not deadlock on one id."""
    from app.services import llm_client as mod

    mod._REJECTED_GEMINI_MODELS.add("gemini-3.6-flash")
    client = mod.GeminiClient(api_key="test-key", model_name="gemini-3.6-flash")

    with patch("app.services.llm_client.genai") as fake_genai:
        fake_genai.list_models.side_effect = RuntimeError("network down")
        resolved = client._resolve_model()

    assert resolved != "gemini-3.6-flash"
    assert resolved in mod.FALLBACK_GEMINI_MODELS
