from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Shopping Assistant"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    openai_api_key: str
    openai_chat_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    database_url: str = "sqlite:///./shopping_assistant.db"

    qdrant_path: str = "./qdrant_data"
    qdrant_collection_name: str = "product_docs"
    retrieval_top_k: int = 8

    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
