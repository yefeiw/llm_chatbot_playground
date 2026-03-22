# Week 1: System Lives Framework (Claude SDK)

## Goal

- Start a runnable local Agent service.
- Enable basic Agent conversation.
- Prepare a clean foundation for future search integration.

## Project Framework

```text
app/
  api/      # API layer: /healthz and /chat
  agent/    # Claude SDK agent orchestration
  search/   # Search abstraction and provider interfaces
  eval/     # Evaluation scaffolding
  core/     # Shared config, logging, request context
```

## Claude SDK Framework

- Build the core conversational agent with Anthropic's Claude SDK.
- Keep agent logic modular so tools/search can be attached later.
- Use the Anthropic SDK for direct model calls from the agent layer.

## Configuration Framework

- Manage local secrets with `.env`.
- Include `.env.example`.
- Keep `.env` out of version control.
- Required variables:
  - `ANTHROPIC_API_KEY`
  - `MODEL_NAME`
  - `LOG_LEVEL`
  - `MOCK_AGENT_RESPONSE`

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
- `/chat` returns a valid Claude-based response.
- Logs can trace each request by `request_id`.
- `search` and `eval` modules exist as placeholders.

## Claude SDK References

- Anthropic API quickstart: https://docs.anthropic.com/en/docs/quickstart
- Anthropic API overview: https://docs.anthropic.com/en/api/overview
- Python SDK: https://github.com/anthropics/anthropic-sdk-python
- TypeScript SDK: https://github.com/anthropics/anthropic-sdk-typescript
- Claude Code SDK overview: https://docs.anthropic.com/en/docs/claude-code/sdk
