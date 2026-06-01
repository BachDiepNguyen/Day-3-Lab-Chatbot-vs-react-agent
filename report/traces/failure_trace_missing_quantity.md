# Failure/Guardrail Trace: Missing Quantity

- **Scenario**: `email_003`
- **Model**: OpenAI `gpt-4o-mini`
- **Goal**: Avoid generating a quote when quantity is missing.

## Input Summary

```text
Subject: Hỏi giá camera AI
Body: Công ty tôi đang khảo sát giải pháp camera AI. Vui lòng báo giá giúp tôi.
```

The email does not include a specific SKU or quantity.

## ReAct Path

```text
Step 1
Action: read_email({"email_id": "email_003"})
Observation: email asks for camera AI pricing but does not specify quantity

Step 2
Action: search_product({"query": "camera AI"})
Observation: catalog has AI-CAM-200 as a matching product

Step 3
Final Answer: asks customer to provide product/quantity details
```

## Guardrail

The agent did **not** call `calculate_quote`, because quantity is required for a reliable quote. This prevents a hallucinated price total.
