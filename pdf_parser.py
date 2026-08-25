"""
pdf_parser.py
-------------
Extracts shipping data from e-commerce invoice PDFs using pdfplumber.
Supports common formats: Meesho, Flipkart, Amazon, Shiprocket, generic.
"""

import re
import pdfplumber
from typing import Optional


# ---------------------------------------------------------------------------
# Regex patterns for common e-commerce label fields
# ---------------------------------------------------------------------------

TRACKING_PATTERNS = [
    r'(?:AWB|Tracking|Track|Shipment|Consignment)[:\s#-]*([A-Z0-9]{8,25})',
    r'(?:Order\s*ID|Order No|ORDER)[:\s#-]*([A-Z0-9\-]{6,25})',
    r'(?:Pickup\s*Code|OTP|PIN)[:\s]*(\d{4,8})',
    r'\b([A-Z]{2,4}\d{9,20}[A-Z]{0,3})\b',   # standard courier format
    r'\b(\d{12,20})\b',                          # pure numeric long code
]

PIN_CODE_PATTERN = r'\b[1-9][0-9]{5}\b'

RETURN_KEYWORDS = ['return', 'sender', 'from', 'ship from', 'return address', 'sold by', 'return to']
DELIVERY_KEYWORDS = ['ship to', 'deliver to', 'consignee', 'customer', 'bill to', 'to:']
IGNORE_KEYWORDS  = ['thank you', 'terms', 'condition', 'gst', 'cgst', 'sgst', 'igst',
                    'invoice', 'total', 'amount', 'taxable', 'discount', 'subtotal',
                    'payment', 'mode', 'date', 'qty', 'rate', 'price', 'mrp']


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(text: str) -> str:
    """Strip excessive whitespace while preserving newlines."""
    lines = [l.strip() for l in text.splitlines()]
    lines = [l for l in lines if l]
    return '\n'.join(lines)


def _extract_tracking(full_text: str) -> Optional[str]:
    for pattern in TRACKING_PATTERNS:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _extract_order_id(full_text: str) -> Optional[str]:
    pattern = r'(?:Order\s*(?:ID|No|Number|#))[:\s#-]*([A-Z0-9\-]{6,30})'
    match = re.search(pattern, full_text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _is_address_line(line: str) -> bool:
    """Return True if a line looks like part of a postal address."""
    line_lower = line.lower()
    if any(kw in line_lower for kw in IGNORE_KEYWORDS):
        return False
    # Must have some alphabetic content
    if not re.search(r'[A-Za-z]{3,}', line):
        return False
    return True


def _blocks_to_address(lines: list[str]) -> str:
    """Filter and join address-looking lines."""
    addr_lines = [l for l in lines if _is_address_line(l)]
    return '\n'.join(addr_lines[:8])   # cap at 8 lines


def _find_address_after_keyword(full_text: str, keywords: list[str], stop_keywords: list[str]) -> Optional[str]:
    """
    Locate the first occurrence of any keyword and grab the lines that follow
    until a stop keyword or a blank group appears.
    """
    lines = full_text.splitlines()
    start_idx = None
    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in keywords):
            start_idx = i + 1
            break
    if start_idx is None:
        return None

    collected = []
    blank_count = 0
    for line in lines[start_idx:]:
        stripped = line.strip()
        if not stripped:
            blank_count += 1
            if blank_count >= 2:
                break
            continue
        blank_count = 0
        if any(kw in stripped.lower() for kw in stop_keywords + IGNORE_KEYWORDS):
            break
        collected.append(stripped)
        if len(collected) >= 8:
            break

    return _blocks_to_address(collected) if collected else None


def _extract_product_details(full_text: str) -> list[dict]:
    """
    Try to find product rows: lines that have qty + price or look like item descriptions.
    Returns list of {name, qty, price} dicts.
    """
    products = []
    # Look for lines with a number followed by Rs/₹ or a decimal price
    item_pattern = re.compile(
        r'^(.{5,60?}?)\s+(\d{1,3})\s+(?:Rs\.?|₹)?\s*(\d+(?:\.\d{2})?)',
        re.MULTILINE
    )
    for match in item_pattern.finditer(full_text):
        name = match.group(1).strip()
        if any(kw in name.lower() for kw in IGNORE_KEYWORDS):
            continue
        products.append({
            'name': name,
            'qty': match.group(2),
            'price': match.group(3),
        })

    # Fallback: just pick lines that look like product names near "Item" header
    if not products:
        lines = full_text.splitlines()
        in_items = False
        for line in lines:
            low = line.lower()
            if re.search(r'\bitem\b|\bproduct\b|\bdescription\b', low):
                in_items = True
                continue
            if in_items and line.strip():
                # Stop at totals
                if re.search(r'total|subtotal|grand|amount', low):
                    break
                name = line.strip()
                if len(name) > 4:
                    products.append({'name': name, 'qty': '1', 'price': ''})
            if len(products) >= 10:
                break

    return products


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_pdf(file_path: str) -> dict:
    """
    Parse an e-commerce shipping label PDF.

    Returns:
        {
          "customer_address": str,
          "return_address": str,
          "tracking_code": str | None,
          "order_id": str | None,
          "product_details": list[dict],
          "raw_text": str,
          "confidence": {field: "high"|"medium"|"low"}
        }
    """
    all_text_parts = []

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=3, y_tolerance=3)
            if text:
                all_text_parts.append(text)

    full_text = '\n\n'.join(all_text_parts)

    # --- Tracking code ---
    tracking_code = _extract_tracking(full_text)
    order_id      = _extract_order_id(full_text)

    # --- Customer (Ship-To) address ---
    customer_address = _find_address_after_keyword(
        full_text,
        keywords=DELIVERY_KEYWORDS,
        stop_keywords=RETURN_KEYWORDS,
    )
    customer_confidence = 'high' if customer_address else 'low'

    # If keyword-based search failed, try the largest text block with a pincode
    if not customer_address:
        chunks = re.split(r'\n{2,}', full_text)
        for chunk in chunks:
            if re.search(PIN_CODE_PATTERN, chunk) and len(chunk.split()) > 5:
                customer_address = _clean(chunk)
                customer_confidence = 'medium'
                break

    # --- Return address ---
    return_address = _find_address_after_keyword(
        full_text,
        keywords=RETURN_KEYWORDS,
        stop_keywords=DELIVERY_KEYWORDS,
    )
    return_confidence = 'high' if return_address else 'low'

    if not return_address:
        # Fallback: first address block before the customer address
        chunks = re.split(r'\n{2,}', full_text)
        for chunk in chunks:
            chunk_clean = chunk.strip()
            if (re.search(PIN_CODE_PATTERN, chunk_clean)
                    and chunk_clean != customer_address
                    and len(chunk_clean.split()) > 4):
                return_address = _clean(chunk_clean)
                return_confidence = 'medium'
                break

    # --- Product details ---
    product_details = _extract_product_details(full_text)

    return {
        'customer_address': customer_address or '',
        'return_address':   return_address   or '',
        'tracking_code':    tracking_code    or '',
        'order_id':         order_id         or '',
        'product_details':  product_details,
        'raw_text':         full_text,
        'confidence': {
            'customer_address': customer_confidence,
            'return_address':   return_confidence,
            'tracking_code':    'high' if tracking_code else 'low',
        },
    }
