from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ProductResult(BaseModel):
    product_uid: str
    title: str
    brand: str
    category: str
    description: str
    price_cents: int | None = None
    image_url: str | None = None
    product_url: str | None = None
    rating: float | None = None
    review_count: int | None = None
    score: float | None = None
    specs: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    products: list[ProductResult]
