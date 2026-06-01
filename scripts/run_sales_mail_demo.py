import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from src.agent.agent import ReActAgent
from src.baseline.chatbot import run_chatbot_baseline
from src.core.mock_provider import MockSalesMailProvider
from src.core.openai_provider import OpenAIProvider
from src.tools.sales_mail_tools import get_sales_mail_tools, read_email


DEFAULT_EMAIL_IDS = ["email_001", "email_002", "email_003", "email_004", "email_005", "email_006"]


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run Sales Mail Agent demo with local fixtures.")
    parser.add_argument("--email-id", action="append", help="Email fixture ID, e.g. email_001. Can be repeated.")
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument(
        "--provider",
        choices=["openai", "mock"],
        default=_default_provider(),
        help="LLM provider to use. Defaults to DEFAULT_PROVIDER from .env, or openai.",
    )
    parser.add_argument(
        "--model",
        default=_default_model(),
        help="Model name for OpenAI provider. Defaults to DEFAULT_MODEL from .env, or gpt-4o-mini.",
    )
    args = parser.parse_args()

    email_ids = args.email_id or DEFAULT_EMAIL_IDS
    llm = _build_provider(args.provider, args.model)
    tools = get_sales_mail_tools()
    agent = ReActAgent(llm=llm, tools=tools, max_steps=args.max_steps)
    print(f"Using provider={args.provider}, model={llm.model_name}")

    results: List[Dict[str, object]] = []
    for email_id in email_ids:
        email = read_email(email_id)
        email_text = _format_email_for_baseline(email)
        print("=" * 80)
        print(f"EMAIL: {email_id} | {email.get('subject', 'unknown')}")

        baseline = run_chatbot_baseline(llm, email_text)
        print("\n[Chatbot baseline]")
        print(baseline["content"])

        agent_answer = agent.run(f"Process local email fixture {email_id}.")
        print("\n[ReAct Agent]")
        print(agent_answer)
        print(f"\n[Agent stats] {json.dumps(agent.last_run_stats, ensure_ascii=False)}")

        results.append(
            {
                "email_id": email_id,
                "baseline": baseline["content"],
                "agent": agent_answer,
                "agent_stats": agent.last_run_stats,
            }
        )

    output_path = ROOT_DIR / "report" / "sales_mail_demo_results.json"
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=" * 80)
    print(f"Saved demo results to {output_path}")


def _format_email_for_baseline(email: Dict[str, object]) -> str:
    if email.get("error"):
        return json.dumps(email, ensure_ascii=False)
    attachments = ", ".join(email.get("attachments", [])) or "none"
    return (
        f"From: {email.get('from')}\n"
        f"Subject: {email.get('subject')}\n"
        f"Attachments: {attachments}\n\n"
        f"{email.get('body')}"
    )


def _build_provider(provider: str, model: str):
    if provider == "mock":
        return MockSalesMailProvider()
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is missing. Add it to .env or run with --provider mock.")
        return OpenAIProvider(model_name=_normalize_model_name(model), api_key=api_key)
    raise ValueError(f"Unsupported provider: {provider}")


def _default_provider() -> str:
    provider = os.getenv("DEFAULT_PROVIDER", "openai").lower()
    return provider if provider in {"openai", "mock"} else "openai"


def _default_model() -> str:
    return _normalize_model_name(os.getenv("DEFAULT_MODEL", "gpt-4o-mini"))


def _normalize_model_name(model: str) -> str:
    if model == "gpt-40-mini":
        return "gpt-4o-mini"
    return model


if __name__ == "__main__":
    main()
