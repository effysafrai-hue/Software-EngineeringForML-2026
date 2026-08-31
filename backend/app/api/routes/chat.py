from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.chat import ChatMessage
from app.models.user import User
from app.schemas.chat import ChatMessageResponse, ChatRequest, ChatResponse
from app.services.ai_agent import process_chat
from app.services.chat_queue import chat_queue, Priority

router = APIRouter(prefix="/chat", tags=["AI Chat"])


@router.post("", response_model=ChatResponse)
async def send_chat_message(
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

    ai_result = await chat_queue.submit(
        Priority.INTERACTIVE_CHAT,
        process_chat,
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


@router.get("/history", response_model=List[ChatMessageResponse])
def get_chat_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id, ChatMessage.shared_calendar_id == None)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return messages
