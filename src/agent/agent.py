import ast
import csv
import inspect
import json
import re
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker


class ReActAgent:
    """
    A ReAct-style Agent that follows the Thought-Action-Observation loop.
    Tools are passed as dictionaries with: name, description, function.
    """

    ACTION_RE = re.compile(
        r"Action\s*:\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)\s*$",
        re.IGNORECASE | re.DOTALL | re.MULTILINE,
    )
    FINAL_RE = re.compile(r"Final Answer\s*:\s*(.*)", re.IGNORECASE | re.DOTALL)

    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]], max_steps: int = 5):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.history: List[Dict[str, Any]] = []
        self.last_run_stats: Dict[str, Any] = {}

    def get_system_prompt(self) -> str:
        tool_descriptions = "\n".join(
            [
                f"- {tool['name']}: {tool['description']}"
                for tool in self.tools
            ]
        )
        return f"""
You are Sales Mail Agent, an assistant for processing customer sales emails.
Your job is to classify quote/order requests, read attachments when needed,
look up product data, verify inventory, calculate quotes, and draft a reply.

Available tools:
{tool_descriptions}

Rules:
- Use product prices, stock, discounts, and VAT only from tools. Never invent them.
- If the email references an attachment, call extract_attachment_text before pricing.
- If product SKU/name or quantity is missing, ask for the missing information in Final Answer.
- If an email is unrelated to sales, return Final Answer without pricing tools.
- Customer-facing reply content must be in Vietnamese.
- When calling draft_reply_email, provide a complete Vietnamese context, not a placeholder.
- Use at most one Action per response.
- After every Observation, continue reasoning from the updated evidence.

Output format:
Thought: concise reasoning about the next step.
Action: tool_name({{"argument": "value"}})

When the task is complete, output:
Final Answer: your final answer in Vietnamese, including the recommended draft reply if relevant.
""".strip()

    def run(self, user_input: str) -> str:
        logger.log_event(
            "AGENT_START",
            {"input": user_input, "model": self.llm.model_name, "max_steps": self.max_steps},
        )

        self.history = []
        scratchpad = f"User request:\n{user_input}\n"

        for step in range(1, self.max_steps + 1):
            result = self.llm.generate(scratchpad, system_prompt=self.get_system_prompt())
            content = result.get("content", "").strip()

            usage = result.get("usage", {})
            if usage:
                tracker.track_request(
                    result.get("provider", self.llm.__class__.__name__),
                    self.llm.model_name,
                    usage,
                    result.get("latency_ms", 0),
                )

            logger.log_event(
                "AGENT_STEP",
                {
                    "step": step,
                    "llm_output": content,
                    "latency_ms": result.get("latency_ms", 0),
                    "usage": usage,
                },
            )

            final_answer = self._parse_final_answer(content)
            if final_answer:
                self.last_run_stats = {
                    "status": "completed",
                    "steps": step,
                    "tool_calls": len([h for h in self.history if h.get("type") == "tool_call"]),
                }
                logger.log_event("AGENT_END", self.last_run_stats)
                return final_answer

            action = self._parse_action(content)
            if not action:
                observation = (
                    "Parser error: no valid Action or Final Answer found. "
                    "Use Action: tool_name({\"argument\": \"value\"}) or Final Answer: ..."
                )
                logger.log_event(
                    "AGENT_PARSE_ERROR",
                    {"step": step, "llm_output": content, "observation": observation},
                )
                scratchpad += f"\n{content}\nObservation: {observation}\n"
                self.history.append(
                    {"type": "parse_error", "step": step, "content": content, "observation": observation}
                )
                continue

            tool_name, raw_args = action
            observation = self._execute_tool(tool_name, raw_args)
            logger.log_event(
                "AGENT_TOOL_CALL",
                {
                    "step": step,
                    "tool": tool_name,
                    "raw_args": raw_args,
                    "observation": observation,
                },
            )
            self.history.append(
                {
                    "type": "tool_call",
                    "step": step,
                    "tool": tool_name,
                    "raw_args": raw_args,
                    "observation": observation,
                }
            )
            scratchpad += f"\n{content}\nObservation: {observation}\n"

        self.last_run_stats = {
            "status": "timeout",
            "steps": self.max_steps,
            "tool_calls": len([h for h in self.history if h.get("type") == "tool_call"]),
        }
        logger.log_event("AGENT_TIMEOUT", self.last_run_stats)
        return "Tôi chưa thể hoàn tất trong giới hạn bước hiện tại. Vui lòng kiểm tra logs để xem trace chi tiết."

    def _parse_final_answer(self, content: str) -> Optional[str]:
        match = self.FINAL_RE.search(content)
        if not match:
            return None
        return match.group(1).strip()

    def _parse_action(self, content: str) -> Optional[Tuple[str, str]]:
        cleaned = self._strip_code_fences(content)
        matches = list(self.ACTION_RE.finditer(cleaned))
        if not matches:
            return None
        match = matches[-1]
        return match.group(1).strip(), match.group(2).strip()

    def _execute_tool(self, tool_name: str, args: str) -> str:
        tool = next((item for item in self.tools if item["name"] == tool_name), None)
        if not tool:
            return self._json_dumps({"error": "tool_not_found", "tool": tool_name})

        function = tool.get("function")
        if not callable(function):
            return self._json_dumps({"error": "tool_has_no_callable", "tool": tool_name})

        try:
            parsed_args = self._parse_args(args)
            result = self._call_function(function, parsed_args)
            return self._json_dumps(result)
        except Exception as exc:
            logger.log_event(
                "AGENT_TOOL_ERROR",
                {"tool": tool_name, "raw_args": args, "error": str(exc)},
            )
            return self._json_dumps({"error": "tool_execution_failed", "tool": tool_name, "message": str(exc)})

    def _parse_args(self, args: str) -> Any:
        cleaned = args.strip()
        if not cleaned:
            return {}

        for parser in (json.loads, ast.literal_eval):
            try:
                return parser(cleaned)
            except Exception:
                pass

        return [self._coerce_scalar(value) for value in self._split_csv(cleaned)]

    def _call_function(self, function: Any, parsed_args: Any) -> Any:
        if isinstance(parsed_args, dict):
            return function(**parsed_args)
        if isinstance(parsed_args, (list, tuple)):
            return function(*parsed_args)

        signature = inspect.signature(function)
        if len(signature.parameters) == 0:
            return function()
        return function(parsed_args)

    def _split_csv(self, value: str) -> List[str]:
        reader = csv.reader(StringIO(value), skipinitialspace=True)
        return next(reader)

    def _coerce_scalar(self, value: str) -> Any:
        stripped = value.strip().strip("\"'")
        lowered = stripped.lower()
        if lowered in {"true", "false"}:
            return lowered == "true"
        try:
            return int(stripped)
        except ValueError:
            pass
        try:
            return float(stripped)
        except ValueError:
            return stripped

    def _strip_code_fences(self, content: str) -> str:
        return re.sub(r"```(?:json|text)?\s*|\s*```", "", content, flags=re.IGNORECASE)

    def _json_dumps(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, indent=2)
