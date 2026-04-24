from openai import OpenAI

from app.core.config import settings


SYSTEM_PROMPT = """You are a product-only shopping assistant.
Rules:
- Use only provided product context.
- If information is not in context, say you cannot confirm.
- The backend has already ranked the retrieved products and selected the variant for each product.
- The ranked product cards are shown separately in the UI.
- Do not list products, enumerate product names, or repeat card details.
- Do not say a different product should be first.
- Write a concise 2-4 sentence summary of how the cards were ranked and what tradeoffs to scan.
- Refer to cards by rank only if needed, not by product model name.
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
