# AGENTS.md

## Claude SDK Research Notes

### What do we mean by "Claude SDK" in this repo?

For this repo, **Claude SDK** should primarily mean Anthropic's official API SDKs for calling Claude from application code.
That is the most natural fit for a local agent service with `/chat` and `/healthz` endpoints.

A second, related meaning is the **Claude Code SDK**, which is better suited to agent-harness workflows, tool execution, and MCP-driven integrations.

## Official Links

### Anthropic API and SDKs
- Anthropic API quickstart: https://docs.anthropic.com/en/docs/quickstart
- Anthropic API overview: https://docs.anthropic.com/en/api/overview
- Python SDK repository: https://github.com/anthropics/anthropic-sdk-python
- TypeScript SDK repository: https://github.com/anthropics/anthropic-sdk-typescript

### Claude Code SDK
- Claude Code SDK overview: https://docs.anthropic.com/en/docs/claude-code/sdk
- Claude Code quickstart: https://docs.anthropic.com/en/docs/claude-code/quickstart
- MCP in the Claude Code SDK: https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-mcp

## Repo Direction

- Use **Anthropic API SDKs** as the default path for the app scaffold.
- Keep the agent layer clean so Claude Code SDK or MCP-style integrations can be evaluated later if needed.
