from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.debug import router as debug_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.models import Base
from app.db.session import engine

configure_logging()
app = FastAPI(title=settings.app_name)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(chat_router)
app.include_router(debug_router)
