# Week 1: System Lives Framework (Google ADK)

## Goal

- Start a runnable local Agent service.
- Enable basic Agent conversation.
- Prepare a clean foundation for future search integration.

## Project Framework

```text
app/
  api/      # API layer: /healthz and /chat
  agent/    # Google ADK agent definition and orchestration
  search/   # Search abstraction and provider interfaces
  eval/     # Evaluation scaffolding
  core/     # Shared config, logging, request context
```

## Google ADK Framework

- Build the core conversational agent with Google ADK.
- Keep agent logic modular so tools/search can be attached later.
- Use ADK runtime patterns for request handling and agent execution.

## Configuration Framework

- Manage local secrets with `.env`.
- Include `.env.example`.
- Keep `.env` out of version control.

### Authentication Options (align with ADK docs)

Use **one** of the following:

1. **Gemini Developer API mode**
   - `GOOGLE_API_KEY`

2. **Vertex AI mode**
   - `GOOGLE_GENAI_USE_VERTEXAI=true`
   - `GOOGLE_CLOUD_PROJECT=<your-project-id>`
   - `GOOGLE_CLOUD_LOCATION=<your-region>` (for example `us-central1`)

Additional shared setting:
- `MODEL_NAME`
- `LOG_LEVEL`

## API Framework

- `GET /healthz`
  - Returns service health status.
- `POST /chat`
  - Input: user message payload.
  - Output: agent reply, model name, request ID.

## Observability Framework

- Generate or propagate `request_id` for each request.
- Log structured fields:
  - `path`
  - `status_code`
  - `latency_ms`
  - `request_id`

## Done Criteria

- Local Agent API starts successfully.
- `/healthz` responds with a healthy status.
- `/chat` returns a valid ADK-based response.
- Logs can trace each request by `request_id`.
- `search` and `eval` modules exist as placeholders.

## ADK References

- Google ADK docs home: https://google.github.io/adk-docs/
- ADK Quickstart: https://google.github.io/adk-docs/get-started/quickstart/
- ADK Agents: https://google.github.io/adk-docs/agents/
- ADK Tools: https://google.github.io/adk-docs/tools/
- ADK Sessions and Memory: https://google.github.io/adk-docs/sessions/
