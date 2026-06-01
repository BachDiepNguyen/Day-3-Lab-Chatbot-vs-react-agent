# Technical Failure Trace: Parser Error and Unknown Tool

This trace documents the kind of technical failure handling expected in Lab 3. It is covered by tests in `tests/test_agent_failures.py`.

## Parser Error Recovery

When the model output has no valid `Action:` and no `Final Answer:`, the agent records `AGENT_PARSE_ERROR` and feeds the observation back into the scratchpad.

```text
LLM output:
I should probably do something, but I will not use the required format.

Observation:
Parser error: no valid Action or Final Answer found.
Use Action: tool_name({"argument": "value"}) or Final Answer: ...
```

Expected behavior:

```text
The next LLM turn can recover and produce a valid Final Answer.
```

## Unknown Tool Guardrail

When the model calls a tool that is not registered:

```text
Action: made_up_tool({"x": 1})
```

The agent returns a structured observation instead of crashing:

```json
{
  "error": "tool_not_found",
  "tool": "made_up_tool"
}
```

Expected behavior:

```text
The agent can use this observation to stop, retry with a valid tool, or produce a final answer explaining the failure.
```
