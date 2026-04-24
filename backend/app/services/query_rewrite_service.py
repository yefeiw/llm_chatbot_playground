from __future__ import annotations

from openai import OpenAI

from app.core.config import settings


QUERY_REWRITE_SYSTEM_PROMPT = """You rewrite shopping-assistant turns into standalone product retrieval queries.
Rules:
- Return only the rewritten query text.
- Use the latest user request as the primary intent.
- Carry forward relevant product category, budget, attributes, and comparison context from the conversation.
- If the latest user request is already standalone, return it unchanged.
- Do not answer the user and do not add unsupported details.
"""


class QueryRewriteService:
    def __init__(self, client: OpenAI | None = None) -> None:
        self.client = client or OpenAI(api_key=settings.openai_api_key)

    def rewrite(self, user_message: str, memory_text: str) -> str:
        original_query = user_message.strip()
        if not original_query:
            return original_query

        input_text = (
            f"Conversation history, oldest to newest:\n{memory_text or '(none)'}\n\n"
            f"Latest user request:\n{original_query}\n\n"
            "Write a concise standalone query for product vector retrieval."
        )
        response = self.client.responses.create(
            model=settings.openai_chat_model,
            input=[
                {"role": "system", "content": QUERY_REWRITE_SYSTEM_PROMPT},
                {"role": "user", "content": input_text},
            ],
            max_output_tokens=120,
        )
        return self._clean_rewrite(response.output_text, fallback=original_query)

    @staticmethod
    def _clean_rewrite(text: str, fallback: str) -> str:
        cleaned = " ".join(text.strip().strip("\"'").split())
        return cleaned or fallback
