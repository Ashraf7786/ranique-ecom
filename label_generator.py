"""
label_generator.py
------------------
Generates 4×4" and 4×6" shipping label PDFs using reportlab.
Includes store branding + QR code section for the 4×6 format.
"""

import io
import qrcode
from PIL import Image as PILImage
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MARGIN = 0.15 * inch

# Store info (hardcoded as per requirements)
STORE_NAME    = "raniquelifestyle"
STORE_ADDRESS = (
    "Rani Shringar & Cosmetic Store\n"
    "Near Surya Mandir, Obra\n"
    "Aurangabad, Bihar – 824124"
)
STORE_QR_DATA = (
    "https://maps.google.com/?q=Rani+Shringar+Cosmetic+Store,"
    "+Near+Surya+Mandir,+Obra,+Aurangabad,+Bihar+824124"
)

# Colors
COLOR_BLACK    = colors.black
COLOR_WHITE    = colors.white
COLOR_DARK     = HexColor('#1a1a2e')
COLOR_ACCENT   = HexColor('#f4a438')   # Ranique saffron/orange
COLOR_SUBTLE   = HexColor('#444444')
COLOR_DIVIDER  = HexColor('#cccccc')
COLOR_STORE_BG = HexColor('#fdf6ec')   # warm cream for store section


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_qr_image(data: str, size_px: int = 180) -> PILImage.Image:
    """Return a PIL Image of the QR code."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    img = img.resize((size_px, size_px), PILImage.NEAREST)
    return img.convert('RGB')


def _pil_to_reader(pil_image: PILImage.Image) -> ImageReader:
    """Convert a PIL image to a reportlab ImageReader."""
    buf = io.BytesIO()
    pil_image.save(buf, format='PNG')
    buf.seek(0)
    return ImageReader(buf)


def _draw_multiline(c: canvas.Canvas, text: str, x: float, y: float,
                    max_width: float, font: str, size: float,
                    leading: float | None = None, color=COLOR_BLACK) -> float:
    """
    Draw multi-line text. Returns the Y position after the last line.
    Performs simple word-wrap if a single line exceeds max_width.
    """
    if leading is None:
        leading = size * 1.35

    c.setFont(font, size)
    c.setFillColor(color)

    raw_lines = text.splitlines()
    output_lines: list[str] = []

    for raw in raw_lines:
        words = raw.split()
        if not words:
            output_lines.append('')
            continue
        current = ''
        for word in words:
            test = (current + ' ' + word).strip()
            if c.stringWidth(test, font, size) <= max_width:
                current = test
            else:
                if current:
                    output_lines.append(current)
                current = word
        if current:
            output_lines.append(current)

    for line in output_lines:
        c.drawString(x, y, line)
        y -= leading

    return y


def _draw_divider(c: canvas.Canvas, y: float, x_start: float, x_end: float,
                  thickness: float = 0.5, color=COLOR_DIVIDER) -> None:
    c.setStrokeColor(color)
    c.setLineWidth(thickness)
    c.line(x_start, y, x_end, y)


def _draw_label_border(c: canvas.Canvas, width: float, height: float) -> None:
    c.setStrokeColor(COLOR_SUBTLE)
    c.setLineWidth(0.5)
    c.rect(MARGIN / 2, MARGIN / 2, width - MARGIN, height - MARGIN)


def _draw_section_header(c: canvas.Canvas, text: str, x: float, y: float,
                          width: float, bg_color=COLOR_ACCENT,
                          text_color=COLOR_WHITE, font_size: float = 7) -> float:
    """Draw a small pill-style section label. Returns y after the header."""
    pill_h = font_size + 4
    c.setFillColor(bg_color)
    c.roundRect(x, y - pill_h + 2, width, pill_h, 2, fill=1, stroke=0)
    c.setFillColor(text_color)
    c.setFont('Helvetica-Bold', font_size)
    c.drawCentredString(x + width / 2, y - pill_h + 4, text.upper())
    return y - pill_h - 3


# ---------------------------------------------------------------------------
# 4×4 Label
# ---------------------------------------------------------------------------

def generate_4x4(data: dict) -> bytes:
    """
    Generate a 4×4 inch (288×288pt) shipping label.
    Returns PDF bytes.
    """
    W = 4 * inch
    H = 4 * inch
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))

    _draw_label_border(c, W, H)

    x0 = MARGIN
    x1 = W - MARGIN
    content_w = x1 - x0
    y = H - MARGIN

    # ── Top bar ──────────────────────────────────────────────────────────────
    c.setFillColor(COLOR_DARK)
    c.rect(0, H - 0.22 * inch, W, 0.22 * inch, fill=1, stroke=0)
    c.setFillColor(COLOR_WHITE)
    c.setFont('Helvetica-Bold', 7)
    c.drawCentredString(W / 2, H - 0.22 * inch + 5, 'SHIPPING LABEL')
    y = H - 0.22 * inch - 6

    # ── Return Address ───────────────────────────────────────────────────────
    y = _draw_section_header(c, '↩ Return Address', x0, y, content_w * 0.55,
                              bg_color=COLOR_SUBTLE, font_size=6)
    y = _draw_multiline(c, data.get('return_address', '—'),
                        x0, y, content_w, 'Helvetica', 6.5,
                        color=COLOR_SUBTLE)
    y -= 6

    # ── Divider ──────────────────────────────────────────────────────────────
    _draw_divider(c, y, x0, x1, thickness=0.4)
    y -= 10

    # ── Customer Address ─────────────────────────────────────────────────────
    y = _draw_section_header(c, '✈ Ship To', x0, y, content_w * 0.4, font_size=6.5)
    y = _draw_multiline(c, data.get('customer_address', '—'),
                        x0, y, content_w, 'Helvetica-Bold', 10.5,
                        leading=14)
    y -= 8

    # ── Order ID (small, right-aligned) ──────────────────────────────────────
    order_id = data.get('order_id', '')
    if order_id:
        c.setFont('Helvetica', 7)
        c.setFillColor(COLOR_SUBTLE)
        c.drawRightString(x1, y, f'Order: {order_id}')
        y -= 12

    # ── Bottom Tracking Section ───────────────────────────────────────────────
    tracking_h = 0.65 * inch
    ty = MARGIN + tracking_h
    _draw_divider(c, ty, x0, x1, thickness=0.6)

    # Tracking code text
    tracking_code = data.get('tracking_code', '')
    c.setFillColor(COLOR_DARK)
    c.rect(x0, MARGIN, content_w, tracking_h - 2, fill=1, stroke=0)

    c.setFillColor(COLOR_ACCENT)
    c.setFont('Helvetica-Bold', 6)
    c.drawString(x0 + 4, MARGIN + tracking_h - 12, 'TRACKING CODE')

    c.setFillColor(COLOR_WHITE)
    c.setFont('Helvetica-Bold', 13)
    c.drawCentredString(W / 2, MARGIN + tracking_h / 2 - 6, tracking_code or 'N/A')

    c.save()
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 4×6 Label
# ---------------------------------------------------------------------------

def generate_4x6(data: dict) -> bytes:
    """
    Generate a 4×6 inch (288×432pt) shipping label with store section.
    Returns PDF bytes.
    """
    W = 4 * inch
    H = 6 * inch
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))

    _draw_label_border(c, W, H)

    x0 = MARGIN
    x1 = W - MARGIN
    content_w = x1 - x0

    # ── Zone boundaries ──────────────────────────────────────────────────────
    store_zone_h = 2.0 * inch
    divider_y    = MARGIN + store_zone_h          # ~144pt + 10.8pt
    ship_zone_h  = H - divider_y - MARGIN         # top shipping zone

    # ══ SHIPPING ZONE (top 3.5 inches approx) ══════════════════════════════

    y = H - MARGIN

    # Top dark header bar
    c.setFillColor(COLOR_DARK)
    c.rect(0, H - 0.25 * inch, W, 0.25 * inch, fill=1, stroke=0)
    c.setFillColor(COLOR_WHITE)
    c.setFont('Helvetica-Bold', 8)
    c.drawCentredString(W / 2, H - 0.25 * inch + 6, 'SHIPPING LABEL')
    y = H - 0.25 * inch - 8

    # Return address
    y = _draw_section_header(c, '↩ Return Address', x0, y, content_w * 0.55,
                              bg_color=COLOR_SUBTLE, font_size=6)
    y = _draw_multiline(c, data.get('return_address', '—'),
                        x0, y, content_w, 'Helvetica', 7,
                        leading=10, color=COLOR_SUBTLE)
    y -= 10

    # Divider between return and ship-to
    _draw_divider(c, y, x0, x1, thickness=0.4)
    y -= 10

    # Customer address (larger, prominent)
    y = _draw_section_header(c, '✈ Ship To', x0, y, content_w * 0.4, font_size=7)
    y = _draw_multiline(c, data.get('customer_address', '—'),
                        x0, y, content_w, 'Helvetica-Bold', 11,
                        leading=15)
    y -= 8

    # Order ID
    order_id = data.get('order_id', '')
    if order_id:
        c.setFont('Helvetica', 7.5)
        c.setFillColor(COLOR_SUBTLE)
        c.drawRightString(x1, y, f'Order: {order_id}')
        y -= 14

    # Tracking code band (just above the main divider)
    tracking_band_h = 0.72 * inch
    band_y = divider_y + 3
    c.setFillColor(COLOR_DARK)
    c.roundRect(x0, band_y, content_w, tracking_band_h, 4, fill=1, stroke=0)

    c.setFillColor(COLOR_ACCENT)
    c.setFont('Helvetica-Bold', 6.5)
    c.drawString(x0 + 6, band_y + tracking_band_h - 14, 'TRACKING CODE')

    tracking_code = data.get('tracking_code', '')
    c.setFillColor(COLOR_WHITE)
    c.setFont('Helvetica-Bold', 14)
    c.drawCentredString(W / 2, band_y + tracking_band_h / 2 - 8, tracking_code or 'N/A')

    # ══ MAIN DIVIDER ════════════════════════════════════════════════════════
    c.setFillColor(COLOR_ACCENT)
    c.rect(0, divider_y - 1.5, W, 3, fill=1, stroke=0)

    # ══ STORE ZONE (bottom 2 inches) ════════════════════════════════════════
    # Warm background
    c.setFillColor(COLOR_STORE_BG)
    c.rect(0, MARGIN / 2, W, store_zone_h + MARGIN / 2, fill=1, stroke=0)

    sy = divider_y - 6   # start drawing store zone from here (going down)

    # "STORE LABEL" pill header
    pill_y = sy - 14
    c.setFillColor(COLOR_ACCENT)
    c.roundRect(x0, pill_y, content_w, 14, 3, fill=1, stroke=0)
    c.setFillColor(COLOR_WHITE)
    c.setFont('Helvetica-Bold', 7)
    c.drawCentredString(W / 2, pill_y + 3, '★  STORE LABEL  ★')

    # QR code — 1×1 inch, bottom-right
    qr_size = 1.0 * inch
    qr_x    = x1 - qr_size
    qr_y    = MARGIN + 4

    qr_img  = _generate_qr_image(STORE_QR_DATA, size_px=200)
    qr_reader = _pil_to_reader(qr_img)
    c.drawImage(qr_reader, qr_x, qr_y, width=qr_size, height=qr_size,
                preserveAspectRatio=True)

    # QR label
    c.setFont('Helvetica', 5)
    c.setFillColor(COLOR_SUBTLE)
    c.drawCentredString(qr_x + qr_size / 2, qr_y - 7, 'Scan for directions')

    # Store name (large)
    text_x   = x0
    text_maxw = qr_x - x0 - 4
    store_ty = pill_y - 6

    c.setFont('Helvetica-Bold', 13)
    c.setFillColor(COLOR_DARK)
    c.drawString(text_x, store_ty, STORE_NAME)
    store_ty -= 4

    # Accent underline beneath store name
    name_w = c.stringWidth(STORE_NAME, 'Helvetica-Bold', 13)
    c.setStrokeColor(COLOR_ACCENT)
    c.setLineWidth(1.5)
    c.line(text_x, store_ty, text_x + name_w, store_ty)
    store_ty -= 8

    # Store address lines
    _draw_multiline(c, STORE_ADDRESS,
                    text_x, store_ty, text_maxw,
                    'Helvetica', 7, leading=10,
                    color=COLOR_SUBTLE)

    c.save()
    return buf.getvalue()
