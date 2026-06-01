from typing import Any, Dict

from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker


BASELINE_SYSTEM_PROMPT = """
You are a helpful sales assistant. Reply to the customer email directly.
Do not use tools. If you do not know exact price, stock, or discount, say that
a salesperson must verify the data before sending an official quote.
""".strip()


def run_chatbot_baseline(llm: LLMProvider, email_text: str) -> Dict[str, Any]:
    """
    Direct LLM response without tools. This is the baseline for comparison.
    """
    logger.log_event("CHATBOT_BASELINE_START", {"model": llm.model_name})
    result = llm.generate(email_text, system_prompt=BASELINE_SYSTEM_PROMPT)

    usage = result.get("usage", {})
    if usage:
        tracker.track_request(
            result.get("provider", llm.__class__.__name__),
            llm.model_name,
            usage,
            result.get("latency_ms", 0),
        )

    output = {
        "content": result.get("content", "").strip(),
        "latency_ms": result.get("latency_ms", 0),
        "usage": usage,
    }
    logger.log_event("CHATBOT_BASELINE_END", output)
    return output
