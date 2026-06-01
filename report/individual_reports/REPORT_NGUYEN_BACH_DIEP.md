# Individual Report: Lab 3 - Sales Mail ReAct Agent

- **Student Name**: Nguyễn Bách Điệp
- **Student ID**: 2A202600535
- **Date**: 2026-06-01
- **Model Used**: OpenAI `gpt-4o-mini`

---

## I. Technical Contribution

I contributed to the implementation of a Sales Mail ReAct Agent for processing customer quote/order emails.

- Implemented the ReAct loop in `src/agent/agent.py`: LLM call, action parsing, tool execution, observation feedback, final answer detection, timeout handling, and telemetry.
- Implemented sales tools in `src/tools/sales_mail_tools.py`: email reading, attachment extraction, product search, inventory check, quote calculation, and draft email creation.
- Added local fixtures in `data/`: email samples, RFQ attachment, product catalog, inventory, and pricing rules.
- Added chatbot baseline in `src/baseline/chatbot.py` for direct LLM comparison.
- Added OpenAI execution support in `scripts/run_sales_mail_demo.py` and kept `MockSalesMailProvider` for offline tests.
- Added tests for tools and ReAct scenarios in `tests/test_sales_mail_tools.py` and `tests/test_react_agent.py`.

---

## II. Debugging Case Study

### Problem

The agent must not generate a quote when important information is missing or unverifiable.

### Case 1: Missing Quantity

Input: `email_003`, asking for a camera AI quote without specifying product SKU or quantity.

Observed trace:

```text
Action: read_email({"email_id": "email_003"})
Action: search_product({"query": "camera AI"})
Final Answer: asks customer to provide product/quantity details
```

Diagnosis: the product category can be inferred, but the quote requires exact product and quantity. Calling `calculate_quote` would create an unreliable quote.

Solution: the system prompt requires the agent to ask for missing SKU/name or quantity instead of guessing. The scenario test verifies that `calculate_quote` is not called.

### Case 2: Unknown Product

Input: `email_006`, requesting 10 units of `ROBOT-X9`.

Observed trace:

```text
Action: read_email({"email_id": "email_006"})
Action: search_product({"query": "ROBOT-X9"})
Observation: {"found": false, "error": "product_not_found"}
Action: draft_reply_email(...)
Final Answer: asks customer to verify product name/details
```

Diagnosis: the product was not found in catalog, so the agent correctly avoided pricing and inventory assumptions.

Solution: tool-backed catalog lookup is mandatory before quoting unknown SKUs.

---

## III. Personal Insights: Chatbot vs ReAct

The chatbot baseline is useful for writing polite responses, but it cannot safely answer operational questions. In the final OpenAI run, the chatbot often said a salesperson must verify the data. This is appropriate but not enough for automation.

The ReAct Agent performs better for business workflows because it separates reasoning from facts. Prices come from `calculate_quote`, stock comes from `check_inventory`, and attachment content comes from `extract_attachment_text`. This makes the final answer auditable through logs.

The tradeoff is cost and latency. The final run used 1,329 baseline tokens versus 25,191 agent tokens. The agent is more expensive, but it produces verified quotes and failure-handled responses.

---

## IV. Future Improvements

- Replace local email fixtures with Gmail API or Microsoft Graph API.
- Replace local catalog/inventory JSON files with ERP/CRM APIs.
- Add PDF, DOCX, XLSX, and OCR support for real attachments.
- Add human approval before sending any draft email.
- Add prompt-injection detection for attachment text.
- Add real OpenAI pricing tables for cost telemetry.
