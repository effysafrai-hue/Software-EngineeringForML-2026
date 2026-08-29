import logging
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.course import Course, CourseReview
from app.services.course_grounding import compute_embedding

logger = logging.getLogger("seed_courses")
logger.setLevel(logging.INFO)

COURSES_DATA = [
    {
        "code": "CS101",
        "name": "Introduction to Computer Science & Programming in Python",
        "description": "Foundational computer science principles, computational problem solving, control flow, functions, recursion, and object-oriented programming using Python.",
        "syllabus_topics": [
            "Variables, Types, and Expressions",
            "Control Flow & Conditionals",
            "Functions & Variable Scope",
            "Recursion & Algorithmic Thinking",
            "Data Structures (Lists, Tuples, Dictionaries, Sets)",
            "Object-Oriented Programming (Classes & Inheritance)",
            "File I/O and Exception Handling",
        ],
        "reviews": [
            {"rating": 5, "review_text": "Great course for beginners! The Python assignments are well-structured.", "author": "Alice"},
            {"rating": 4, "review_text": "Clear explanation of recursion and OOP concepts.", "author": "Bob"},
        ],
    },
    {
        "code": "CS229",
        "name": "Machine Learning",
        "description": "Comprehensive mathematical and algorithmic foundation of machine learning, covering supervised learning, unsupervised learning, and reinforcement learning.",
        "syllabus_topics": [
            "Linear Regression & Gradient Descent",
            "Logistic Regression & Generalized Linear Models",
            "Support Vector Machines (SVMs) & Kernel Methods",
            "Neural Networks & Backpropagation",
            "Decision Trees & Random Forests",
            "K-Means Clustering & Expectation Maximization",
            "Principal Component Analysis (PCA)",
            "Reinforcement Learning & MDPs",
        ],
        "reviews": [
            {"rating": 5, "review_text": "Demanding math and rigorous proofs, but the gold standard for ML foundations.", "author": "Charlie"},
            {"rating": 5, "review_text": "Essential preparation for research in AI and deep learning.", "author": "Dana"},
        ],
    },
    {
        "code": "CS224N",
        "name": "Natural Language Processing with Deep Learning",
        "description": "State-of-the-art computational linguistics and deep learning architectures for NLP, transformers, large language models, and alignment.",
        "syllabus_topics": [
            "Word Vectors & Distributed Representations (Word2Vec, GloVe)",
            "Recurrent Neural Networks (RNNs) & LSTMs",
            "Sequence-to-Sequence & Attention Mechanisms",
            "Transformer Architecture & Self-Attention Mechanics",
            "Pretrained Foundation Models (BERT, GPT, T5)",
            "In-Context Learning & Prompt Engineering",
            "Instruction Tuning, RLHF, and Safety Alignment",
            "Retrieval-Augmented Generation (RAG)",
        ],
        "reviews": [
            {"rating": 5, "review_text": "Superb hands-on PyTorch transformer implementation homeworks.", "author": "Elena"},
            {"rating": 5, "review_text": "The lectures on attention mechanisms and LLM alignment are cutting edge.", "author": "Farhan"},
        ],
    },
    {
        "code": "CS145",
        "name": "Data Management and Databases",
        "description": "Database system architecture, relational design, SQL optimization, transactions, ACID properties, and distributed NoSQL databases.",
        "syllabus_topics": [
            "Relational Model & Relational Algebra",
            "SQL Querying & Query Optimization",
            "Schema Normalization (1NF, 2NF, 3NF, BCNF)",
            "B+ Tree Indexing & Hash Tables",
            "ACID Transactions & Two-Phase Locking",
            "Write-Ahead Logging (WAL) & Crash Recovery",
            "NoSQL Key-Value & Document Stores (MongoDB, DynamoDB)",
        ],
        "reviews": [
            {"rating": 4, "review_text": "Practical database design exercises and heavy SQL optimization drills.", "author": "Grace"},
        ],
    },
    {
        "code": "MATH21",
        "name": "Linear Algebra & Matrix Theory",
        "description": "Vector spaces, linear transformations, matrices, determinants, eigenvalues, eigenvectors, and singular value decomposition.",
        "syllabus_topics": [
            "Vector Spaces & Subspaces",
            "Linear Independence, Basis, and Dimension",
            "Matrix Operations & Inverses",
            "Orthogonal Projections & Gram-Schmidt",
            "Eigenvalues & Eigenvectors",
            "Singular Value Decomposition (SVD) & Spectral Theorem",
        ],
        "reviews": [
            {"rating": 5, "review_text": "Vital mathematical foundation for anyone taking machine learning or computer graphics.", "author": "Hannah"},
        ],
    },
]


def seed_courses_data(db: Session) -> None:
    for c_data in COURSES_DATA:
        existing = db.query(Course).filter(Course.code == c_data["code"]).first()
        if existing:
            continue

        full_text = f"{c_data['name']} ({c_data['code']}): {c_data['description']} Syllabus: {', '.join(c_data['syllabus_topics'])}"
        emb = compute_embedding(full_text)

        course = Course(
            code=c_data["code"],
            name=c_data["name"],
            description=c_data["description"],
            syllabus_topics=c_data["syllabus_topics"],
            embedding=emb,
        )
        db.add(course)
        db.commit()
        db.refresh(course)

        for r_data in c_data["reviews"]:
            rev = CourseReview(
                course_id=course.id,
                rating=r_data["rating"],
                review_text=r_data["review_text"],
                author=r_data.get("author", "Anonymous"),
            )
            db.add(rev)
        db.commit()
        logger.info(f"Seeded course {course.code}: {course.name}")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_courses_data(db)
        print("Course database successfully seeded!")
    finally:
        db.close()
