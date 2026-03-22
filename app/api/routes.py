import json
import time

from app.agent.service import AgentService
from app.api.schemas import ChatRequest, ChatResponse
from app.core.logging import get_logger
from app.core.request_id import ensure_request_id

logger = get_logger(__name__)
agent_service = AgentService()
JSON_HEADERS = [("Content-Type", "application/json; charset=utf-8")]


def _finalize(status_code: int, request_id: str, path: str, started_at: float, payload: dict) -> tuple[int, list[tuple[str, str]], dict]:
    latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
    logger.info(
        "http.request",
        extra={
            "request_id": request_id,
            "path": path,
            "status_code": status_code,
            "latency_ms": latency_ms,
        },
    )
    response_headers = JSON_HEADERS + [("X-Request-ID", request_id)]
    return status_code, response_headers, payload


def handle_request(method: str, path: str, headers: dict[str, str], body: bytes) -> tuple[int, list[tuple[str, str]], dict]:
    request_id = ensure_request_id(headers.get("X-REQUEST-ID"))
    started_at = time.perf_counter()

    if method == "GET" and path == "/healthz":
        return _finalize(200, request_id, path, started_at, {"status": "ok", "service": "agent-api"})

    if method == "POST" and path == "/chat":
        try:
            payload = ChatRequest.model_validate_json(body or b"{}")
        except ValueError as exc:
            return _finalize(400, request_id, path, started_at, {"error": str(exc), "request_id": request_id})

        result = agent_service.reply(message=payload.message, session_id=payload.session_id, request_id=request_id)
        logger.info(
            "chat.completed",
            extra={
                "request_id": request_id,
                "message_length": len(payload.message),
                "model": result.model,
                "used_search": result.used_search,
            },
        )
        response = ChatResponse(
            reply=result.reply,
            model=result.model,
            request_id=request_id,
            used_search=result.used_search,
        )
        return _finalize(200, request_id, path, started_at, json.loads(response.model_dump_json()))

    return _finalize(404, request_id, path, started_at, {"error": "not_found", "request_id": request_id})
