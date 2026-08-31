import asyncio
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

    # Submit holding task (takes the 1 worker), then low priority (3), then high priority (1)
    t_hold = asyncio.create_task(queue.submit(Priority.BACKGROUND_SUMMARY, hold_worker))
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
