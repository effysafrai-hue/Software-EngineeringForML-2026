import hashlib
import logging
import re
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.course import Course, CourseReview

logger = logging.getLogger("course_grounding")
logger.setLevel(logging.DEBUG)

try:
    import google.generativeai as genai
except ImportError:
    genai = None


def compute_embedding(text: str) -> List[float]:
    if settings.GEMINI_API_KEY and genai is not None:
        for emb_model in ["models/text-embedding-004", "models/embedding-001"]:
            try:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                result = genai.embed_content(
                    model=emb_model,
                    content=text,
                    task_type="retrieval_document",
                )
                if "embedding" in result and result["embedding"]:
                    emb = result["embedding"]
                    if len(emb) == 768:
                        return emb
                    elif len(emb) > 768:
                        return emb[:768]
                    else:
                        return emb + [0.0] * (768 - len(emb))
            except Exception:
                continue

    hash_digest = hashlib.sha256(text.encode("utf-8")).digest()
    vector = []
    for i in range(768):
        byte_val = hash_digest[i % len(hash_digest)]
        vector.append(float((byte_val - 128) / 128.0))
    return vector


# Short words that read as a course-code prefix but are ordinary English, e.g.
# the "for 45" in "... consultation for 45 minutes". Without this filter any
# short word followed by a 2-4 digit number looks like a course code.
_NON_COURSE_PREFIXES = {
    "am", "pm", "at", "by", "in", "of", "on", "to", "up", "or", "no", "be",
    "do", "is", "it", "an", "the", "and", "off", "per", "was", "all", "add",
    "for", "from", "with", "have", "has", "get", "got", "next", "last",
    "past", "till", "only", "over", "just", "take", "about", "after",
    "room", "floor", "level", "page", "unit", "step", "day", "days",
}

_COURSE_CODE_RE = re.compile(r"\b([a-zA-Z]{2,5})\s?(\d{2,4}[a-zA-Z]?)\b")


def extract_course_codes(message: str) -> List[tuple]:
    """Return (prefix, number) pairs from the message that plausibly name a course."""
    return [
        (prefix, number)
        for prefix, number in _COURSE_CODE_RE.findall(message)
        if prefix.lower() not in _NON_COURSE_PREFIXES
    ]


def detect_course_query(message: str) -> bool:
    msg = message.lower()
    if extract_course_codes(msg):
        return True

    keywords = [
        "course", "courses", "class", "classes", "syllabus", "curriculum",
        "prerequisite", "prerequisites", "cover", "covers", "taught", "teach",
        "teaches", "lecture", "lectures", "professor", "review", "reviews",
        "rating", "ratings", "assignment", "homework", "exam", "midterm",
        "study", "learn", "topic", "topics", "subject", "material", "concepts",
        "linear algebra", "eigenvalue", "eigenvalues", "matrix", "matrices",
        "algebra", "calculus", "probability", "statistics", "math",
        "machine learning", "deep learning", "neural", "nlp", "database", "databases",
        "python", "programming", "algorithms", "data structures", "sql",
    ]
    return any(re.search(rf"\b{re.escape(k)}\b", msg) for k in keywords)


def retrieve_relevant_courses(
    query: str,
    db: Session,
    top_k: int = 3,
) -> Dict[str, Any]:
    is_course_related = detect_course_query(query)
    logger.info(f"Course query detection for '{query}': {is_course_related}")

    if not is_course_related:
        return {
            "query_is_course_related": False,
            "found": False,
            "courses": [],
            "grounding_text": "",
        }

    matched_courses: List[Course] = []
    seen_ids = set()

    # Step 1: Extract and match explicit course codes
    code_matches = extract_course_codes(query)
    for prefix, number in code_matches:
        candidate_code = f"{prefix.upper()}{number.upper()}"
        course = db.query(Course).filter(Course.code.ilike(candidate_code)).first()
        if course and course.id not in seen_ids:
            matched_courses.append(course)
            seen_ids.add(course.id)

    # Step 2: Keyword search across title, description, and syllabus topics
    stopwords = {
        "the", "what", "does", "this", "that", "with", "from", "about",
        "and", "for", "are", "how", "where", "who", "why", "can", "you",
        "have", "has", "had", "was", "were", "will", "would", "could",
        "should", "did", "not", "but", "also", "into", "its", "our",
        "any", "all", "each", "some", "more", "most", "than", "then",
        "when", "which", "there", "their", "them", "they", "been", "being",
        "other", "out", "over", "own", "very", "just", "too", "only",
        "need", "tell", "give", "know", "want", "study", "learn",
    }
    query_tokens = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2 and w not in stopwords]
    if query_tokens and len(matched_courses) < top_k:
        all_courses = db.query(Course).all()
        scored_candidates: List[tuple] = []
        for course in all_courses:
            if course.id in seen_ids:
                continue
            topics_text = " ".join([str(t).lower() for t in (course.syllabus_topics or [])])
            desc_text = course.description.lower()
            name_text = course.name.lower()
            combined_text = f"{name_text} {desc_text} {topics_text}"

            matches_count = sum(1 for token in query_tokens if token in combined_text)
            if matches_count >= 1:
                scored_candidates.append((matches_count, course))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        for _score, course in scored_candidates:
            if len(matched_courses) >= top_k:
                break
            matched_courses.append(course)
            seen_ids.add(course.id)

    found = len(matched_courses) > 0
    grounding_blocks = []

    if found:
        for course in matched_courses:
            topics_str = "\n".join([f"  - {t}" for t in (course.syllabus_topics or [])])
            reviews_list = []
            for r in course.reviews[:3]:
                reviews_list.append(f"  - {r.rating}/5 stars ({r.author}): \"{r.review_text}\"")
            reviews_str = "\n".join(reviews_list) if reviews_list else "  - No student reviews yet."

            block = (
                f"Course Code: {course.code}\n"
                f"Course Name: {course.name}\n"
                f"Description: {course.description}\n"
                f"Official Syllabus Topics Covered:\n{topics_str}\n"
                f"Student Reviews:\n{reviews_str}"
            )
            grounding_blocks.append(block)

        grounding_text = (
            "=== VERIFIED COURSE KNOWLEDGE BASE CONTEXT (FROM DATABASE) ===\n"
            + "\n---\n".join(grounding_blocks)
            + "\n=============================================================="
        )
    else:
        grounding_text = (
            "=== VERIFIED COURSE KNOWLEDGE BASE CONTEXT (FROM DATABASE) ===\n"
            "NO MATCHING COURSES FOUND IN DATABASE FOR THIS QUERY.\n"
            "=============================================================="
        )

    return {
        "query_is_course_related": is_course_related,
        "found": found,
        "courses": [
            {
                "id": c.id,
                "code": c.code,
                "name": c.name,
                "description": c.description,
                "syllabus_topics": c.syllabus_topics,
                "reviews": [
                    {"rating": r.rating, "review_text": r.review_text, "author": r.author}
                    for r in c.reviews
                ],
            }
            for c in matched_courses
        ],
        "grounding_text": grounding_text,
    }
