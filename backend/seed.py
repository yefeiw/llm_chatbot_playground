from app.db.models import Base
from app.db.session import SessionLocal, engine
from app.services.embed_service import EmbedService
from app.services.ingestion_service import IngestionService
from app.services.retrieval_service import get_retrieval_service


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        service = IngestionService(embed_service=EmbedService(), retrieval_service=get_retrieval_service())
        result = service.seed_and_index(db, total_products=1000)
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
