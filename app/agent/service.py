from dataclasses import dataclass

from app.core.config import get_settings
from app.search.noop import NoopSearchProvider


@dataclass
class AgentResult:
    reply: str
    model: str
    used_search: bool = False


class AgentService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.search_provider = NoopSearchProvider()

    def reply(self, message: str, session_id: str | None, request_id: str) -> AgentResult:
        _ = session_id, request_id
        used_search = False
        if self.settings.mock_agent_response:
            return AgentResult(
                reply=f"[mock:{self.settings.model_name}] You said: {message}",
                model=self.settings.model_name,
                used_search=used_search,
            )

        return AgentResult(
            reply=(
                "Claude SDK integration is not wired yet. "
                "Set MOCK_AGENT_RESPONSE=true for local scaffolding."
            ),
            model=self.settings.model_name,
            used_search=used_search,
        )
