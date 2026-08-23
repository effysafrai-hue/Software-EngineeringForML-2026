from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import ChatMessage, User
from app.schemas.chat import ChatMessageResponse, ChatRequest, ChatResponse
from app.services.ai_agent import process_chat

router = APIRouter(prefix="/chat", tags=["AI Chat"])


@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a message to the Gemini AI Calendar Assistant",
)
def send_chat_message(
    chat_req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not chat_req.message.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message content cannot be empty",
        )

    user_msg = ChatMessage(
        user_id=current_user.id,
        role="user",
        content=chat_req.message,
    )
    db.add(user_msg)
    db.commit()

    ai_result = process_chat(
        message=chat_req.message,
        user_id=current_user.id,
        db=db,
    )

    assistant_msg = ChatMessage(
        user_id=current_user.id,
        role="assistant",
        content=ai_result["reply"],
    )
    db.add(assistant_msg)
    db.commit()

    return ChatResponse(
        reply=ai_result["reply"],
        action_taken=ai_result.get("action_taken"),
    )


@router.get(
    "/history",
    response_model=List[ChatMessageResponse],
    summary="Retrieve chat message history for the current user",
)
def get_chat_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return messages
