from datetime import datetime, timezone
import pytest
from app.models import Course, CourseReview
from app.db.seed_courses import seed_courses_data
from app.services.ai_agent import process_chat
from app.services.course_grounding import retrieve_relevant_courses

MOCK_NOW = datetime(2026, 6, 10, 10, 0, 0, tzinfo=timezone.utc)

# Marked at module level rather than per-test: the autouse fixture below calls
# seed_courses_data, whose compute_embedding hits the Gemini embeddings endpoint
# whenever a key is configured. That makes even the pure-retrieval test in this
# file a network test. Excluded from the default run; see pytest.ini.
pytestmark = pytest.mark.live_llm


@pytest.fixture(autouse=True)
def seed_courses_for_tests(db_session):
    seed_courses_data(db_session)


def test_query_real_course_returns_grounded_info(client, auth_headers_user_a, db_session):
    prompt = "What topics are covered in CS101?"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] is None
    reply_lower = res["reply"].lower()

    assert "python" in reply_lower
    assert any(topic in reply_lower for topic in ["recursion", "control flow", "object-oriented", "functions", "variables"])


def test_query_nonexistent_course_returns_explicit_unknown(client, auth_headers_user_a, db_session):
    prompt = "Can you give me the syllabus for CS999 Advanced Quantum Propulsion?"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] is None
    reply_lower = res["reply"].lower()

    assert any(phrase in reply_lower for phrase in [
        "don't have information",
        "do not have information",
        "no information",
        "not found",
        "don't know",
        "do not know",
        "not in",
        "not listed",
    ])


def test_reverse_fact_check_gentle_correction(client, auth_headers_user_a, db_session):
    prompt = "I heard CS101 covers quantum computing and cryptography, is that true?"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] is None
    reply_lower = res["reply"].lower()

    assert any(neg in reply_lower for neg in ["not", "does not", "doesn't", "actually", "instead", "focuses on"])
    assert "python" in reply_lower


def test_hybrid_retrieval_service_direct(db_session):
    res_code = retrieve_relevant_courses("CS101", db_session)
    assert res_code["found"] is True
    assert res_code["courses"][0]["code"] == "CS101"

    res_kw = retrieve_relevant_courses("Where do we study linear algebra and eigenvalues?", db_session)
    assert res_kw["found"] is True
    assert any(c["code"] == "MATH21" for c in res_kw["courses"])

    res_none = retrieve_relevant_courses("Tell me about BIO999", db_session)
    assert res_none["found"] is False
    assert "NO MATCHING COURSES" in res_none["grounding_text"]
