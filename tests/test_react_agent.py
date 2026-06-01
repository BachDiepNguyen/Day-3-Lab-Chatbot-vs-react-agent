from src.agent.agent import ReActAgent
from src.core.mock_provider import MockSalesMailProvider
from src.tools.sales_mail_tools import get_sales_mail_tools


def build_agent(max_steps=8):
    return ReActAgent(
        llm=MockSalesMailProvider(),
        tools=get_sales_mail_tools(),
        max_steps=max_steps,
    )


def test_agent_completes_quote_request():
    agent = build_agent()
    answer = agent.run("Process local email fixture email_001.")
    tool_names = [event["tool"] for event in agent.history if event["type"] == "tool_call"]

    assert "yêu cầu báo giá" in answer
    assert "search_product" in tool_names
    assert "check_inventory" in tool_names
    assert "calculate_quote" in tool_names
    assert "draft_reply_email" in tool_names
    assert agent.last_run_stats["status"] == "completed"


def test_agent_asks_for_missing_quantity():
    agent = build_agent()
    answer = agent.run("Process local email fixture email_003.")
    tool_names = [event["tool"] for event in agent.history if event["type"] == "tool_call"]

    assert "thiếu số lượng" in answer
    assert "search_product" in tool_names
    assert "calculate_quote" not in tool_names


def test_agent_reads_attachment_before_quote():
    agent = build_agent(max_steps=8)
    answer = agent.run("Process local email fixture email_004.")
    tool_names = [event["tool"] for event in agent.history if event["type"] == "tool_call"]

    assert "attachment" in answer.lower() or "đính kèm" in answer
    assert tool_names[0] == "read_email"
    assert "extract_attachment_text" in tool_names
    assert tool_names.count("calculate_quote") == 2


def test_agent_does_not_price_unrelated_email():
    agent = build_agent()
    answer = agent.run("Process local email fixture email_005.")
    tool_names = [event["tool"] for event in agent.history if event["type"] == "tool_call"]

    assert "không liên quan" in answer
    assert tool_names == ["read_email"]
