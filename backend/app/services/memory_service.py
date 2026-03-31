from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Message, Session as ChatSession


class MemoryService:
    def ensure_session(self, db: Session, session_uid: str) -> None:
        exists = db.scalar(select(ChatSession).where(ChatSession.session_uid == session_uid))
        if not exists:
            db.add(ChatSession(session_uid=session_uid))
            db.commit()

    def add_message(self, db: Session, session_uid: str, role: str, content: str) -> None:
        db.add(Message(session_uid=session_uid, role=role, content=content))
        db.commit()

    def get_messages(self, db: Session, session_uid: str) -> list[Message]:
        result = db.scalars(
            select(Message).where(Message.session_uid == session_uid).order_by(Message.created_at.asc(), Message.id.asc())
        )
        return list(result)
