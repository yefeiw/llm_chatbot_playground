import uuid


def ensure_request_id(request_id: str | None) -> str:
    if request_id and request_id.strip():
        return request_id.strip()
    return str(uuid.uuid4())
