from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.event import Event
from app.models.user import User
from app.schemas.event import EventCreate, EventResponse, EventUpdate

router = APIRouter(prefix="/events", tags=["Calendar Events"])


@router.get(
    "",
    response_model=List[EventResponse],
    summary="List calendar events for the current user",
)
def list_events(
    start_time: Optional[datetime] = Query(
        None, description="Filter events ending on or after this ISO datetime"
    ),
    end_time: Optional[datetime] = Query(
        None, description="Filter events starting on or before this ISO datetime"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Event).filter(Event.user_id == current_user.id)

    if start_time is not None:
        query = query.filter(Event.end_time >= start_time)
    if end_time is not None:
        query = query.filter(Event.start_time <= end_time)

    return query.order_by(Event.start_time.asc()).all()


@router.post(
    "",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new calendar event",
)
def create_event(
    event_in: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = Event(
        user_id=current_user.id,
        title=event_in.title,
        description=event_in.description,
        start_time=event_in.start_time,
        end_time=event_in.end_time,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return event


@router.get(
    "/{event_id}",
    response_model=EventResponse,
    summary="Get a specific calendar event",
)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    if event.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this event",
        )

    return event


@router.patch(
    "/{event_id}",
    response_model=EventResponse,
    summary="Update a calendar event",
)
def update_event(
    event_id: int,
    event_update: EventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    if event.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this event",
        )

    update_data = event_update.model_dump(exclude_unset=True)

    effective_start = update_data.get("start_time", event.start_time)
    effective_end = update_data.get("end_time", event.end_time)

    if effective_end <= effective_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_time must be strictly after start_time",
        )

    for field, value in update_data.items():
        setattr(event, field, value)

    db.commit()
    db.refresh(event)

    return event


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a calendar event",
)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    if event.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this event",
        )

    db.delete(event)
    db.commit()
    return None
