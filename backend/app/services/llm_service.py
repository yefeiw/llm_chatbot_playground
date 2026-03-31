from openai import OpenAI

from app.core.config import settings


SYSTEM_PROMPT = """You are a product-only shopping assistant.
Rules:
- Use only provided product context.
- If information is not in context, say you cannot confirm.
- Keep answers concise and practical.
- Prefer comparisons and recommendations based on stated user preferences.
"""


class LLMService:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key)

    def generate_answer(self, user_message: str, memory_text: str, retrieval_text: str) -> str:
        input_text = (
            f"Conversation history:\n{memory_text}\n\n"
            f"Retrieved product context:\n{retrieval_text}\n\n"
            f"User request:\n{user_message}"
        )

        response = self.client.responses.create(
            model=settings.openai_chat_model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": input_text},
            ],
        )
        return response.output_text
