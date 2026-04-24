from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ProductResult(BaseModel):
    rank: int | None = None
    product_uid: str
    title: str
    brand: str
    category: str
    description: str
    variant_uid: str | None = None
    variant_name: str | None = None
    price_cents: int | None = None
    image_url: str | None = None
    product_url: str | None = None
    rating: float | None = None
    review_count: int | None = None
    score: float | None = None
    evidence: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    rank_summary: str | None = None
    specs: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    products: list[ProductResult]


class AgentStep(BaseModel):
    step: int
    action: str
    action_input: str | None = None
    observation: str


class ReActChatResponse(ChatResponse):
    retrieval_query: str
    agent_steps: list[AgentStep] = Field(default_factory=list)
