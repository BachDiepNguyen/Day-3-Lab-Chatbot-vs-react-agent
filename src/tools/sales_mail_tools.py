import json
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
EMAIL_DIR = DATA_DIR / "emails"
ATTACHMENT_DIR = DATA_DIR / "attachments"


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _normalize(value: str) -> str:
    return value.strip().lower()


def read_email(email_id: str) -> Dict[str, Any]:
    """
    Read a local email fixture by ID. This simulates an email API for the lab.
    """
    path = EMAIL_DIR / f"{email_id}.json"
    if not path.exists():
        return {"error": "email_not_found", "email_id": email_id}
    return _load_json(path)


def extract_attachment_text(file_path: str) -> Dict[str, Any]:
    """
    Extract text from a lab attachment. Supports txt, md, csv, and json files.
    """
    path = Path(file_path)
    if not path.is_absolute():
        path = ROOT_DIR / path
    if not path.exists():
        fallback = ATTACHMENT_DIR / file_path
        path = fallback if fallback.exists() else path
    if not path.exists():
        return {"error": "attachment_not_found", "file_path": file_path}

    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".csv"}:
        return {
            "file_path": str(path.relative_to(ROOT_DIR)),
            "content_type": suffix.removeprefix("."),
            "text": path.read_text(encoding="utf-8"),
        }
    if suffix == ".json":
        return {
            "file_path": str(path.relative_to(ROOT_DIR)),
            "content_type": "json",
            "text": json.dumps(_load_json(path), ensure_ascii=False, indent=2),
        }
    return {"error": "unsupported_attachment_type", "file_path": file_path, "supported": ["txt", "md", "csv", "json"]}


def search_product(query: str) -> Dict[str, Any]:
    """
    Search product catalog by SKU or product name.
    """
    products = _load_json(DATA_DIR / "products.json")
    normalized_query = _normalize(query)
    for product in products:
        sku = _normalize(product["sku"])
        name = _normalize(product["name"])
        aliases = [_normalize(alias) for alias in product.get("aliases", [])]
        if normalized_query == sku or normalized_query in name or normalized_query in aliases:
            return {"found": True, "product": product}
    return {"found": False, "error": "product_not_found", "query": query}


def check_inventory(sku: str, quantity: int) -> Dict[str, Any]:
    """
    Check whether requested quantity is available for a SKU.
    """
    inventory = _load_json(DATA_DIR / "inventory.json")
    requested = int(quantity)
    available = int(inventory.get(sku.upper(), 0))
    return {
        "sku": sku.upper(),
        "requested_quantity": requested,
        "available_quantity": available,
        "is_available": available >= requested,
        "shortage": max(requested - available, 0),
    }


def calculate_quote(sku: str, quantity: int, include_vat: bool = True, customer_type: str = "standard") -> Dict[str, Any]:
    """
    Calculate subtotal, discount, VAT, and final quote total for a SKU.
    """
    product_result = search_product(sku)
    if not product_result.get("found"):
        return {"error": "product_not_found", "sku": sku}

    rules = _load_json(DATA_DIR / "pricing_rules.json")
    product = product_result["product"]
    qty = int(quantity)
    unit_price = int(product["unit_price_vnd"])
    subtotal = unit_price * qty

    discount_percent = _discount_for_quantity(rules.get("quantity_discounts", []), qty)
    customer_discount = int(rules.get("customer_type_discounts", {}).get(customer_type, 0))
    discount_percent += customer_discount
    discount_amount = int(subtotal * discount_percent / 100)
    taxable_amount = subtotal - discount_amount
    vat_rate = float(rules.get("vat_rate", 0.0)) if include_vat else 0.0
    vat_amount = int(taxable_amount * vat_rate)
    total = taxable_amount + vat_amount

    return {
        "sku": product["sku"],
        "product_name": product["name"],
        "quantity": qty,
        "unit_price_vnd": unit_price,
        "subtotal_vnd": subtotal,
        "discount_percent": discount_percent,
        "discount_amount_vnd": discount_amount,
        "vat_rate": vat_rate,
        "vat_amount_vnd": vat_amount,
        "total_vnd": total,
        "currency": "VND",
    }


def draft_reply_email(context: str) -> Dict[str, str]:
    """
    Create a sales reply draft from structured or plain-text context.
    The agent provides the context after it has gathered tool observations.
    """
    normalized_context = _normalize_customer_context(context)
    return {
        "status": "draft_created",
        "draft": (
            "Kính gửi Quý khách,\n\n"
            "Cảm ơn Quý khách đã liên hệ. Dựa trên thông tin hiện có, chúng tôi xin gửi phản hồi sơ bộ:\n"
            f"{normalized_context}\n\n"
            "Báo giá này cần được nhân viên kinh doanh kiểm tra lần cuối trước khi gửi chính thức.\n\n"
            "Trân trọng,\nSales Team"
        ),
    }


def get_sales_mail_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": "read_email",
            "description": "Read a local sales email by ID. Input JSON: {\"email_id\": \"email_001\"}.",
            "function": read_email,
        },
        {
            "name": "extract_attachment_text",
            "description": "Extract text from txt/md/csv/json attachment. Input JSON: {\"file_path\": \"data/attachments/rfq_camera.csv\"}.",
            "function": extract_attachment_text,
        },
        {
            "name": "search_product",
            "description": "Find product by SKU or name. Input JSON: {\"query\": \"AI-CAM-200\"}.",
            "function": search_product,
        },
        {
            "name": "check_inventory",
            "description": "Check stock for a SKU and quantity. Input JSON: {\"sku\": \"AI-CAM-200\", \"quantity\": 50}.",
            "function": check_inventory,
        },
        {
            "name": "calculate_quote",
            "description": "Calculate quote total from catalog price. Input JSON: {\"sku\": \"AI-CAM-200\", \"quantity\": 50, \"include_vat\": true, \"customer_type\": \"standard\"}.",
            "function": calculate_quote,
        },
        {
            "name": "draft_reply_email",
            "description": "Create a Vietnamese reply email draft after facts are gathered. Input JSON: {\"context\": \"quote summary\"}.",
            "function": draft_reply_email,
        },
    ]


def _discount_for_quantity(discounts: List[Dict[str, Any]], quantity: int) -> int:
    discount_percent = 0
    for rule in discounts:
        if quantity >= int(rule["min_quantity"]):
            discount_percent = max(discount_percent, int(rule["discount_percent"]))
    return discount_percent


def _normalize_customer_context(context: str) -> str:
    cleaned = context.strip()
    if cleaned.lower() == "quote summary":
        return "Tóm tắt báo giá đã được tính bằng công cụ. Vui lòng xem phần trả lời cuối của agent để kiểm tra chi tiết từng dòng."
    if "could not find the product" in cleaned.lower() and "ROBOT-X9" in cleaned:
        return (
            "Chúng tôi chưa tìm thấy sản phẩm ROBOT-X9 trong catalog hiện tại. "
            "Quý khách vui lòng kiểm tra lại mã sản phẩm hoặc cung cấp thêm thông tin để chúng tôi hỗ trợ chính xác hơn."
        )
    return cleaned
