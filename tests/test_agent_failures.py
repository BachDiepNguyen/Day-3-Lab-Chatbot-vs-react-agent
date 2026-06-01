from typing import Any, Dict, Generator, Optional

from src.agent.agent import ReActAgent
from src.core.llm_provider import LLMProvider


class ScriptedProvider(LLMProvider):
    def __init__(self, outputs):
        super().__init__(model_name="scripted-test-provider")
        self.outputs = list(outputs)
        self.calls = 0

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        output = self.outputs[min(self.calls, len(self.outputs) - 1)]
        self.calls += 1
        return {
            "content": output,
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "latency_ms": 0,
            "provider": "scripted",
        }

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        yield self.generate(prompt, system_prompt)["content"]


def test_agent_recovers_from_parser_error():
    provider = ScriptedProvider(
        [
            "I should act, but this output has no valid action format.",
            "Final Answer: Parser error was observed and the agent recovered.",
        ]
    )
    agent = ReActAgent(llm=provider, tools=[], max_steps=2)

    answer = agent.run("Trigger parser error.")

    assert "recovered" in answer
    assert agent.history[0]["type"] == "parse_error"
    assert agent.last_run_stats["status"] == "completed"


def test_agent_returns_structured_error_for_unknown_tool():
    provider = ScriptedProvider(
        [
            'Action: made_up_tool({"x": 1})',
            "Final Answer: Unknown tool error was observed.",
        ]
    )
    agent = ReActAgent(llm=provider, tools=[], max_steps=2)

    answer = agent.run("Trigger unknown tool.")

    assert "Unknown tool" in answer
    assert agent.history[0]["type"] == "tool_call"
    assert agent.history[0]["tool"] == "made_up_tool"
    assert "tool_not_found" in agent.history[0]["observation"]
