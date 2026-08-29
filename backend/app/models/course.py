from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator, UserDefinedType
from app.db.session import Base

try:
    from pgvector.sqlalchemy import Vector as PgVector
except ImportError:
    class PgVector(UserDefinedType):
        def __init__(self, dim=768):
            self.dim = dim

        def get_col_spec(self, **kw):
            return f"vector({self.dim})"

        def bind_processor(self, dialect):
            def process(value):
                if value is None:
                    return None
                if isinstance(value, (list, tuple)):
                    return f"[{','.join(str(float(x)) for x in value)}]"
                return str(value)
            return process

        def result_processor(self, dialect, coltype):
            def process(value):
                if value is None:
                    return None
                if isinstance(value, str) and value.startswith("[") and value.endswith("]"):
                    return [float(x.strip()) for x in value[1:-1].split(",") if x.strip()]
                return value
            return process


class SafeVector(TypeDecorator):
    """
    Platform-independent Vector type supporting pgvector on PostgreSQL
    and JSON on SQLite.
    """
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PgVector(768))
        return dialect.type_descriptor(JSON())


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    syllabus_topics = Column(JSON, nullable=False, default=list)
    embedding = Column(SafeVector, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    reviews = relationship(
        "CourseReview",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="CourseReview.created_at.desc()",
    )


class CourseReview(Base):
    __tablename__ = "course_reviews"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    course_id = Column(
        Integer,
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rating = Column(Integer, nullable=False)
    review_text = Column(Text, nullable=False)
    author = Column(String(100), nullable=True, default="Anonymous")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    course = relationship("Course", back_populates="reviews")
