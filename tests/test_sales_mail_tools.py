from src.tools.sales_mail_tools import (
    calculate_quote,
    check_inventory,
    extract_attachment_text,
    read_email,
    search_product,
)


def test_read_email_fixture():
    email = read_email("email_001")
    assert email["id"] == "email_001"
    assert "AI-CAM-200" in email["body"]


def test_search_product_by_sku_and_alias():
    by_sku = search_product("AI-CAM-200")
    by_alias = search_product("camera AI")
    assert by_sku["found"] is True
    assert by_alias["found"] is True
    assert by_sku["product"]["sku"] == "AI-CAM-200"
    assert by_alias["product"]["sku"] == "AI-CAM-200"


def test_search_product_not_found():
    result = search_product("ROBOT-X9")
    assert result["found"] is False
    assert result["error"] == "product_not_found"


def test_check_inventory_available_and_shortage():
    available = check_inventory("AI-CAM-200", 50)
    shortage = check_inventory("IOT-GW-500", 10)
    assert available["is_available"] is True
    assert shortage["is_available"] is False
    assert shortage["shortage"] == 2


def test_calculate_quote_with_vat_and_quantity_discount():
    quote = calculate_quote("AI-CAM-200", 50, include_vat=True)
    assert quote["subtotal_vnd"] == 125000000
    assert quote["discount_percent"] == 5
    assert quote["vat_amount_vnd"] == 11875000
    assert quote["total_vnd"] == 130625000


def test_extract_attachment_text_csv():
    result = extract_attachment_text("data/attachments/rfq_delta.csv")
    assert result["content_type"] == "csv"
    assert "SENSOR-TEMP-10" in result["text"]
