from datetime import datetime, timezone
import pytest
from app.models import Course, CourseReview
from app.db.seed_courses import seed_courses_data
from app.services.ai_agent import process_chat
from app.services.course_grounding import retrieve_relevant_courses

MOCK_NOW = datetime(2026, 6, 10, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def seed_courses_for_tests(db_session):
    """Seed the in-memory test database with courses before each test."""
    seed_courses_data(db_session)


def test_query_real_course_returns_grounded_info(client, auth_headers_user_a, db_session):
    """Querying a real seeded course (CS101) returns factual description and syllabus topics."""
    prompt = "What topics are covered in CS101?"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] is None
    reply_lower = res["reply"].lower()

    assert "python" in reply_lower
    assert any(topic in reply_lower for topic in ["recursion", "control flow", "object-oriented", "functions", "variables"])


def test_query_nlp_course_syllabus(client, auth_headers_user_a, db_session):
    """Querying CS224N returns deep learning and transformer topics from the verified syllabus."""
    prompt = "Tell me about CS224N and what is in the curriculum"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] is None
    reply_lower = res["reply"].lower()

    assert "natural language processing" in reply_lower or "nlp" in reply_lower
    assert any(term in reply_lower for term in ["transformer", "attention", "word vectors", "embeddings", "language models"])


def test_query_nonexistent_course_returns_explicit_unknown(client, auth_headers_user_a, db_session):
    """Asking about a nonexistent course returns an explicit 'I don't have information' / 'I don't know' without hallucination."""
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
    assert "propulsion" not in reply_lower or "don't" in reply_lower or "not" in reply_lower


def test_reverse_fact_check_gentle_correction(client, auth_headers_user_a, db_session):
    """When user asserts a false claim ('CS101 covers quantum computing'), assistant gently corrects them based on DB."""
    prompt = "I heard CS101 covers quantum computing and cryptography, is that true?"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] is None
    reply_lower = res["reply"].lower()

    assert any(neg in reply_lower for neg in ["not", "does not", "doesn't", "actually", "instead", "focuses on"])
    assert "python" in reply_lower


def test_course_reviews_grounding(client, auth_headers_user_a, db_session):
    """Asking for student reviews on CS229 returns real ratings and feedback from the database."""
    prompt = "What do students say about CS229 in their reviews?"
    user_id = 1

    res = process_chat(prompt, user_id=user_id, db=db_session, reference_time=MOCK_NOW)
    assert res["action_taken"] is None
    reply_lower = res["reply"].lower()

    assert any(kw in reply_lower for kw in ["math", "ml", "machine learning", "review", "5", "demanding", "foundation", "gold standard"])


def test_hybrid_retrieval_service(db_session):
    """Unit test for retrieve_relevant_courses service directly."""
    res_code = retrieve_relevant_courses("CS101", db_session)
    assert res_code["found"] is True
    assert res_code["courses"][0]["code"] == "CS101"

    res_kw = retrieve_relevant_courses("Where do we study linear algebra and eigenvalues?", db_session)
    assert res_kw["found"] is True
    assert any(c["code"] == "MATH21" for c in res_kw["courses"])

    res_none = retrieve_relevant_courses("Tell me about BIO999", db_session)
    assert res_none["found"] is False
    assert "NO MATCHING COURSES" in res_none["grounding_text"]
