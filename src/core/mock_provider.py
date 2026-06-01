import json
import re
import time
from typing import Any, Dict, Generator, Optional

from src.core.llm_provider import LLMProvider


class MockSalesMailProvider(LLMProvider):
    """
    Deterministic provider for local demos and tests.
    It behaves like a small scripted LLM so the lab can run without API keys.
    """

    def __init__(self):
        super().__init__(model_name="mock-sales-mail-provider")

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.time()
        content = self._agent_response(prompt) if self._is_agent_prompt(system_prompt) else self._baseline_response(prompt)
        latency_ms = int((time.time() - start_time) * 1000)
        total_tokens = max(1, int((len(prompt) + len(system_prompt or "") + len(content)) / 4))
        return {
            "content": content,
            "usage": {
                "prompt_tokens": max(1, int((len(prompt) + len(system_prompt or "")) / 4)),
                "completion_tokens": max(1, int(len(content) / 4)),
                "total_tokens": total_tokens,
            },
            "latency_ms": latency_ms,
            "provider": "mock",
        }

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        response = self.generate(prompt, system_prompt=system_prompt)["content"]
        for token in response.split():
            yield token + " "

    def _is_agent_prompt(self, system_prompt: Optional[str]) -> bool:
        return bool(system_prompt and "Sales Mail Agent" in system_prompt)

    def _baseline_response(self, prompt: str) -> str:
        if "newsletter" in prompt.lower() or "hội thảo marketing" in prompt.lower():
            return "Email này không phải yêu cầu báo giá hoặc đặt hàng. Không cần xử lý bởi sales."
        return (
            "Tôi có thể hỗ trợ phản hồi email này, nhưng chưa có quyền truy cập catalog, tồn kho "
            "và bảng giá nên không nên gửi báo giá chính thức."
        )

    def _agent_response(self, prompt: str) -> str:
        email_id = self._extract_email_id(prompt)
        observations = self._extract_observations(prompt)

        if email_id:
            if not observations:
                return f'Thought: Cần đọc email local trước khi xử lý.\nAction: read_email({{"email_id": "{email_id}"}})'
            return self._response_for_email_id(email_id, observations)

        return self._response_for_plain_email(prompt, observations)

    def _response_for_email_id(self, email_id: str, observations: str) -> str:
        if email_id == "email_001":
            return self._quote_single_product_flow(observations, "AI-CAM-200", 50)
        if email_id == "email_002":
            return self._quote_single_product_flow(observations, "IOT-GW-500", 4)
        if email_id == "email_003":
            if "search_product" not in observations and "AI-CAM-200" not in observations:
                return 'Thought: Email thiếu số lượng nhưng có thể tra sản phẩm camera AI để xác định SKU.\nAction: search_product({"query": "camera AI"})'
            return (
                "Final Answer: Email là yêu cầu báo giá nhưng thiếu số lượng. "
                "Không tạo báo giá chính thức. Draft reply: Kính gửi Quý khách, vui lòng cho biết số lượng camera AI cần mua để chúng tôi kiểm tra tồn kho và gửi báo giá chính xác."
            )
        if email_id == "email_004":
            return self._attachment_flow(observations)
        if email_id == "email_005":
            return "Final Answer: Email không liên quan đến báo giá hoặc đặt hàng. Không cần gọi tool giá/tồn kho."
        if email_id == "email_006":
            if "product_not_found" not in observations and '"found": false' not in observations:
                return 'Thought: Cần kiểm tra sản phẩm ROBOT-X9 có trong catalog không.\nAction: search_product({"query": "ROBOT-X9"})'
            return (
                "Final Answer: Không tìm thấy sản phẩm ROBOT-X9 trong catalog hiện tại. "
                "Draft reply: Kính gửi Quý khách, hiện chúng tôi chưa có ROBOT-X9 trong danh mục sản phẩm đang bán. Vui lòng gửi thêm thông tin hoặc mã sản phẩm thay thế."
            )
        return "Final Answer: Không có kịch bản xử lý cho email này."

    def _response_for_plain_email(self, prompt: str, observations: str) -> str:
        if "AI-CAM-200" in prompt:
            return self._quote_single_product_flow(observations, "AI-CAM-200", self._extract_quantity(prompt) or 50)
        return "Final Answer: Vui lòng cung cấp email_id hoặc nội dung có SKU và số lượng rõ ràng."

    def _quote_single_product_flow(self, observations: str, sku: str, quantity: int) -> str:
        if '"found": true' not in observations or f'"sku": "{sku}"' not in observations:
            return f'Thought: Cần tra catalog để lấy giá và tên chuẩn của {sku}.\nAction: search_product({{"query": "{sku}"}})'
        if "is_available" not in observations:
            return f'Thought: Đã có sản phẩm, cần kiểm tra tồn kho cho số lượng {quantity}.\nAction: check_inventory({{"sku": "{sku}", "quantity": {quantity}}})'
        if "total_vnd" not in observations:
            return f'Thought: Tồn kho đủ hoặc đã có tồn kho, cần tính báo giá có VAT.\nAction: calculate_quote({{"sku": "{sku}", "quantity": {quantity}, "include_vat": true, "customer_type": "standard"}})'
        if "draft_created" not in observations:
            return (
                "Thought: Đã có dữ liệu báo giá, cần tạo email phản hồi nháp.\n"
                f'Action: draft_reply_email({{"context": "Báo giá cho {quantity} bộ {sku} đã được tính bằng công cụ, có VAT và cần kiểm tra trước khi gửi."}})'
            )
        total = self._latest_json_number(observations, "total_vnd")
        return (
            "Final Answer: Email là yêu cầu báo giá/đặt hàng hợp lệ. "
            f"Agent đã tra catalog, kiểm tra tồn kho, tính báo giá có VAT và tạo draft phản hồi. Tổng dự kiến: {total:,} VND."
        )

    def _attachment_flow(self, observations: str) -> str:
        if "sku,product_name,quantity" not in observations:
            return 'Thought: Email yêu cầu báo giá theo file đính kèm, cần đọc attachment trước.\nAction: extract_attachment_text({"file_path": "data/attachments/rfq_delta.csv"})'
        if "SENSOR-TEMP-10" in observations and "IOT-GW-500" in observations and "total_vnd" not in observations:
            return 'Thought: Cần tính dòng báo giá đầu tiên trong attachment.\nAction: calculate_quote({"sku": "SENSOR-TEMP-10", "quantity": 30, "include_vat": true, "customer_type": "standard"})'
        if '"sku": "SENSOR-TEMP-10"' in observations and '"sku": "IOT-GW-500"' not in observations:
            return 'Thought: Cần tính dòng báo giá thứ hai trong attachment.\nAction: calculate_quote({"sku": "IOT-GW-500", "quantity": 3, "include_vat": true, "customer_type": "standard"})'
        if "draft_created" not in observations:
            return (
                "Thought: Đã tính các dòng báo giá từ attachment, cần tạo email nháp.\n"
                'Action: draft_reply_email({"context": "Báo giá theo file đính kèm gồm SENSOR-TEMP-10 số lượng 30 và IOT-GW-500 số lượng 3, có VAT."})'
            )
        return "Final Answer: Email có attachment RFQ hợp lệ. Agent đã đọc file đính kèm, tính báo giá cho từng SKU và tạo draft phản hồi."

    def _extract_email_id(self, prompt: str) -> str:
        match = re.search(r"\bemail_\d{3}\b", prompt)
        return match.group(0) if match else ""

    def _extract_quantity(self, prompt: str) -> int:
        match = re.search(r"\b(\d+)\s*(?:bộ|cái|pcs|units)?", prompt, re.IGNORECASE)
        return int(match.group(1)) if match else 0

    def _extract_observations(self, prompt: str) -> str:
        marker = "Observation:"
        if marker not in prompt:
            return ""
        return prompt[prompt.find(marker):]

    def _latest_json_number(self, text: str, key: str) -> int:
        matches = re.findall(rf'"{re.escape(key)}"\s*:\s*(\d+)', text)
        return int(matches[-1]) if matches else 0
