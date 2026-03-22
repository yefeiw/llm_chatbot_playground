from dataclasses import dataclass
import json


@dataclass
class ChatRequest:
    message: str
    session_id: str | None = None

    @classmethod
    def model_validate_json(cls, payload: bytes) -> "ChatRequest":
        data = json.loads(payload.decode("utf-8"))
        message = data.get("message")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("message must be a non-empty string")
        session_id = data.get("session_id")
        if session_id is not None and not isinstance(session_id, str):
            raise ValueError("session_id must be a string or null")
        return cls(message=message, session_id=session_id)


@dataclass
class ChatResponse:
    reply: str
    model: str
    request_id: str
    used_search: bool = False

    def model_dump_json(self) -> str:
        return json.dumps(
            {
                "reply": self.reply,
                "model": self.model,
                "request_id": self.request_id,
                "used_search": self.used_search,
            }
        )
