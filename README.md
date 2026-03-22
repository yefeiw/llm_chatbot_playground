# llm_chatbot_playground

Minimal agent-service scaffold for experimenting with different LLM application patterns using the Claude SDK direction for Week 1.

## Run locally

```bash
cp .env.example .env
python3 -m app.main
```

The local server starts on `http://127.0.0.1:8000` by default.

## Endpoints

- `GET /healthz`
- `POST /chat`
