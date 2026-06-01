# Success Trace: RFQ Attachment Email

- **Scenario**: `email_004`
- **Model**: OpenAI `gpt-4o-mini`
- **Goal**: Read an RFQ email with an attached CSV file and produce a quote for all requested products.

## Input Summary

The customer email asks for a quote based on an attached file:

```text
Subject: RFQ theo file đính kèm
Attachment: data/attachments/rfq_delta.csv
```

The attachment contains:

```csv
sku,product_name,quantity,include_vat,destination
SENSOR-TEMP-10,Industrial Temperature Sensor,30,true,Hanoi
IOT-GW-500,IoT Gateway,3,true,Hanoi
```

## ReAct Path

```text
Step 1
Action: read_email({"email_id": "email_004"})
Observation: email has attachment data/attachments/rfq_delta.csv

Step 2
Action: extract_attachment_text({"file_path": "data/attachments/rfq_delta.csv"})
Observation: CSV contains SENSOR-TEMP-10 quantity 30 and IOT-GW-500 quantity 3

Step 3
Action: check_inventory({"sku": "SENSOR-TEMP-10", "quantity": 30})
Observation: available_quantity=36, is_available=true

Step 4
Action: check_inventory({"sku": "IOT-GW-500", "quantity": 3})
Observation: available_quantity=8, is_available=true

Step 5
Action: calculate_quote({"sku": "SENSOR-TEMP-10", "quantity": 30, "include_vat": true})
Observation: total_vnd=27208500

Step 6
Action: calculate_quote({"sku": "IOT-GW-500", "quantity": 3, "include_vat": true})
Observation: total_vnd=13860000

Step 7
Action: draft_reply_email(...)

Step 8
Final Answer: quote draft with both line items
```

## Why This Trace Matters

The baseline chatbot could not inspect the attachment. The ReAct Agent used the attachment extraction, inventory, and pricing tools to produce a grounded quote.
