"""
store_overlay.py
----------------
Takes an existing Meesho PDF label and stamps a store strip.

Layout:
  [ 🏪  STORE NAME (bold) ] | [ QR ]  Follow
                             |        our shop

Uses PyMuPDF + Plus Jakarta Sans (auto-downloaded on first run).
"""

import io
import os
import urllib.request
import math
import pymupdf as fitz
import qrcode
from PIL import Image as PILImage


# ── Store defaults ─────────────────────────────────────────────────────────
DEFAULT_STORE_NAME  = "RANIQUE LIFESTYLE"
DEFAULT_FOLLOW_TEXT = "Follow\nour shop"

# ── Strip constants ────────────────────────────────────────────────────────
STRIP_HEIGHT = 62        # points (~0.86 inch)
STRIP_MARGIN = 8         # gap from page edges
BORDER_WIDTH = 1.5
RADIUS       = 0.1       # rounded corners (PyMuPDF 0-0.5 proportion)

# ── Colors (R,G,B  0-1) ────────────────────────────────────────────────────
COLOR_BLACK = (0.0,  0.0,  0.0)
COLOR_WHITE = (1.0,  1.0,  1.0)
COLOR_GREY  = (0.55, 0.55, 0.55)
COLOR_LIGHT = (0.92, 0.92, 0.92)


# ══════════════════════════════════════════════════════════════════════════
# Font setup  —  Plus Jakarta Sans (auto-download from GitHub releases)
# ══════════════════════════════════════════════════════════════════════════

_HERE      = os.path.dirname(os.path.abspath(__file__))
FONT_DIR   = os.path.join(_HERE, 'fonts')
FONT_BOLD  = os.path.join(FONT_DIR, 'PlusJakartaSans-Bold.ttf')
FONT_SEMI  = os.path.join(FONT_DIR, 'PlusJakartaSans-SemiBold.ttf')
FONT_REG   = os.path.join(FONT_DIR, 'PlusJakartaSans-Regular.ttf')

_FONT_URLS = {
    FONT_BOLD: (
        'https://raw.githubusercontent.com/tokotype/PlusJakartaSans/master'
        '/fonts/ttf/PlusJakartaSans-Bold.ttf'
    ),
    FONT_SEMI: (
        'https://raw.githubusercontent.com/tokotype/PlusJakartaSans/master'
        '/fonts/ttf/PlusJakartaSans-SemiBold.ttf'
    ),
    FONT_REG: (
        'https://raw.githubusercontent.com/tokotype/PlusJakartaSans/master'
        '/fonts/ttf/PlusJakartaSans-Regular.ttf'
    ),
}


def _ensure_fonts() -> None:
    """Download Plus Jakarta Sans TTFs on first run (silent if offline)."""
    os.makedirs(FONT_DIR, exist_ok=True)
    for path, url in _FONT_URLS.items():
        if not os.path.exists(path):
            try:
                urllib.request.urlretrieve(url, path)
                print(f'[font] Downloaded {os.path.basename(path)}')
            except Exception as exc:
                print(f'[font] Could not download {os.path.basename(path)}: {exc}')


_ensure_fonts()   # runs once at module load


def _font_path(bold: bool = True, semi: bool = False) -> str | None:
    if bold and os.path.exists(FONT_BOLD):
        return FONT_BOLD
    if semi and os.path.exists(FONT_SEMI):
        return FONT_SEMI
    if os.path.exists(FONT_REG):
        return FONT_REG
    return None


def _text_width(text: str, size: float, bold: bool = True) -> float:
    """Width of *text* in pts using Jakarta Sans (fallback: Helvetica)."""
    fp = _font_path(bold)
    if fp:
        try:
            return fitz.Font(fontfile=fp).text_length(text, fontsize=size)
        except Exception:
            pass
    return fitz.get_text_length(text,
                                fontname='hebo' if bold else 'helv',
                                fontsize=size)


def _insert(page: fitz.Page, point: fitz.Point, text: str,
            size: float, bold: bool = True,
            color: tuple = COLOR_BLACK) -> None:
    """Insert *text* with Jakarta Sans Bold/Regular (fallback to built-in)."""
    fp = _font_path(bold)
    if fp:
        try:
            page.insert_text(point, text,
                             fontfile=fp,
                             fontname='jakarta-b' if bold else 'jakarta-r',
                             fontsize=size, color=color)
            return
        except Exception:
            pass
    page.insert_text(point, text,
                     fontname='hebo' if bold else 'helv',
                     fontsize=size, color=color)


# ══════════════════════════════════════════════════════════════════════════
# QR code
# ══════════════════════════════════════════════════════════════════════════

def _make_qr_png(url: str, size_px: int = 300) -> bytes:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=7, border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white').convert('RGB')
    img = img.resize((size_px, size_px), PILImage.NEAREST)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════
# Store / shop icon  (drawn with PyMuPDF primitives)
# ══════════════════════════════════════════════════════════════════════════

def _draw_icon(page: fitz.Page, rect: fitz.Rect, icon_type: str) -> None:
    """
    Draws one of 10 modern storefront/shop icons inside *rect*.
    """
    x0, y0, x1, y1 = rect.x0, rect.y0, rect.x1, rect.y1
    pad = 3
    icon_w = min((x1 - x0) - pad * 2, (y1 - y0) - pad * 2)
    icon_h = icon_w
    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2
    ix0 = cx - icon_w / 2
    ix1 = cx + icon_w / 2
    iy0 = cy - icon_h / 2
    iy1 = cy + icon_h / 2
    lw = 1.1

    if icon_type == 'shop':
        # storefront icon
        # Awning
        aw_h  = icon_h * 0.30
        aw_y0 = iy0
        aw_y1 = iy0 + aw_h
        sw    = icon_w / 5
        for i in range(5):
            sx   = ix0 + i * sw
            fill = COLOR_GREY if i % 2 == 0 else COLOR_LIGHT
            page.draw_rect(fitz.Rect(sx, aw_y0, sx + sw, aw_y1),
                           color=fill, fill=fill, width=0.1)
        page.draw_rect(fitz.Rect(ix0, aw_y0, ix1, aw_y1),
                       color=COLOR_BLACK, fill=None, width=lw)

        # Scalloped bottom
        zz_w = icon_w / 5
        zz_h = aw_h * 0.24
        pts  = [fitz.Point(ix0, aw_y1)]
        for i in range(5):
            pts.append(fitz.Point(ix0 + (i + 0.5) * zz_w, aw_y1 + zz_h))
            pts.append(fitz.Point(ix0 + (i + 1.0) * zz_w, aw_y1))
        page.draw_polyline(pts, color=COLOR_BLACK, width=lw)

        # Store body
        body_y0 = aw_y1 + zz_h
        body_h  = iy1 - body_y0
        page.draw_rect(fitz.Rect(ix0, body_y0, ix1, iy1),
                       color=COLOR_BLACK, fill=COLOR_WHITE, width=lw)

        # Signboard
        sw2   = icon_w * 0.58
        sh    = body_h * 0.18
        sx2   = cx - sw2 / 2
        sy2   = body_y0 + body_h * 0.10
        page.draw_rect(fitz.Rect(sx2, sy2, sx2 + sw2, sy2 + sh),
                       color=COLOR_BLACK, fill=COLOR_LIGHT, width=lw * 0.6)

        # Door
        dw  = icon_w * 0.34
        dh  = body_h * 0.52
        dx0 = cx - dw / 2
        dy0 = iy1 - dh
        page.draw_rect(fitz.Rect(dx0, dy0, dx0 + dw, iy1),
                       color=COLOR_BLACK, fill=COLOR_LIGHT, width=lw * 0.8)
        page.draw_circle(fitz.Point(dx0 + dw * 0.28, dy0 + dh * 0.55),
                         lw * 0.9, color=COLOR_BLACK, fill=COLOR_BLACK)

    elif icon_type == 'bag':
        # Shopping Bag
        # Handle
        handle_y = iy0 + icon_h * 0.25
        page.draw_circle(fitz.Point(cx, handle_y), icon_w * 0.20, color=COLOR_BLACK, fill=None, width=lw)
        # Body cover-up
        page.draw_rect(fitz.Rect(ix0, handle_y, ix1, iy1), color=COLOR_WHITE, fill=COLOR_WHITE, width=0)
        # Bag Body
        page.draw_rect(fitz.Rect(ix0, handle_y, ix1, iy1), color=COLOR_BLACK, fill=None, width=lw, radius=0.1)

    elif icon_type == 'cart':
        # Shopping Cart
        # Basket
        by0 = iy0 + icon_h * 0.10
        by1 = iy1 - icon_h * 0.30
        bx0 = ix0 + icon_w * 0.15
        bx1 = ix1 - icon_w * 0.05
        page.draw_rect(fitz.Rect(bx0, by0, bx1, by1), color=COLOR_BLACK, fill=None, width=lw)
        
        # Handle and legs
        page.draw_polyline([
            fitz.Point(ix0, by0),
            fitz.Point(bx0, by0),
            fitz.Point(bx0, by1 + 4),
            fitz.Point(bx1 - 4, by1 + 4)
        ], color=COLOR_BLACK, width=lw)
        
        # Wheels
        wheel_r = icon_h * 0.10
        page.draw_circle(fitz.Point(bx0 + 4, iy1 - wheel_r), wheel_r, color=COLOR_BLACK, fill=COLOR_BLACK)
        page.draw_circle(fitz.Point(bx1 - 6, iy1 - wheel_r), wheel_r, color=COLOR_BLACK, fill=COLOR_BLACK)

    elif icon_type == 'star':
        # Premium Star
        pts = []
        for i in range(10):
            r = (icon_w / 2) if i % 2 == 0 else (icon_w / 4)
            angle = i * math.pi / 5 - math.pi / 2
            pts.append(fitz.Point(cx + r * math.cos(angle), cy + r * math.sin(angle)))
        pts.append(pts[0])
        page.draw_polyline(pts, color=COLOR_BLACK, fill=COLOR_LIGHT, width=lw)

    elif icon_type == 'tag':
        # Price Tag
        tx0 = ix0 + icon_w * 0.15
        tx1 = ix1 - icon_w * 0.15
        ty0 = iy0 + icon_h * 0.15
        ty1 = iy1 - icon_h * 0.15
        page.draw_polyline([
            fitz.Point(cx, ty0),
            fitz.Point(tx1, ty0 + 8),
            fitz.Point(tx1, ty1),
            fitz.Point(tx0, ty1),
            fitz.Point(tx0, ty0 + 8),
            fitz.Point(cx, ty0)
        ], color=COLOR_BLACK, fill=None, width=lw)
        page.draw_circle(fitz.Point(cx, ty0 + 6), 1.5, color=COLOR_BLACK, fill=COLOR_BLACK)

    elif icon_type == 'box':
        # Package / Box
        page.draw_rect(fitz.Rect(ix0, iy0, ix1, iy1), color=COLOR_BLACK, fill=COLOR_WHITE, width=lw)
        page.draw_line(fitz.Point(cx, iy0), fitz.Point(cx, iy1), color=COLOR_BLACK, width=lw * 1.5)
        page.draw_line(fitz.Point(ix0, cy), fitz.Point(ix1, cy), color=COLOR_BLACK, width=lw * 0.5)

    elif icon_type == 'truck':
        # Delivery Truck
        ty0 = iy0 + icon_h * 0.15
        ty1 = iy1 - icon_h * 0.20
        cab_w = icon_w * 0.30
        page.draw_rect(fitz.Rect(ix1 - cab_w, cy - 2, ix1, ty1), color=COLOR_BLACK, fill=COLOR_LIGHT, width=lw)
        page.draw_rect(fitz.Rect(ix0, ty0, ix1 - cab_w - 2, ty1), color=COLOR_BLACK, fill=COLOR_WHITE, width=lw)
        wheel_r = icon_h * 0.10
        page.draw_circle(fitz.Point(ix0 + icon_w * 0.25, ty1 + 2), wheel_r, color=COLOR_BLACK, fill=COLOR_BLACK)
        page.draw_circle(fitz.Point(ix1 - icon_w * 0.25, ty1 + 2), wheel_r, color=COLOR_BLACK, fill=COLOR_BLACK)

    elif icon_type == 'crown':
        # Premium Crown
        cy0 = iy0 + icon_h * 0.20
        page.draw_polyline([
            fitz.Point(ix0, iy1),
            fitz.Point(ix0 + 2, cy0),
            fitz.Point(ix0 + icon_w * 0.3, cy - 2),
            fitz.Point(cx, cy0 - 4),
            fitz.Point(ix1 - icon_w * 0.3, cy - 2),
            fitz.Point(ix1 - 2, cy0),
            fitz.Point(ix1, iy1),
            fitz.Point(ix0, iy1)
        ], color=COLOR_BLACK, fill=COLOR_LIGHT, width=lw)
        page.draw_circle(fitz.Point(ix0 + 2, cy0), 1.2, color=COLOR_BLACK, fill=COLOR_BLACK)
        page.draw_circle(fitz.Point(cx, cy0 - 4), 1.2, color=COLOR_BLACK, fill=COLOR_BLACK)
        page.draw_circle(fitz.Point(ix1 - 2, cy0), 1.2, color=COLOR_BLACK, fill=COLOR_BLACK)

    elif icon_type == 'sparkles':
        # Sparkles / Trendy
        page.draw_polyline([
            fitz.Point(cx, iy0), fitz.Point(cx + 3, cy - 3),
            fitz.Point(ix1, cy), fitz.Point(cx + 3, cy + 3),
            fitz.Point(cx, iy1), fitz.Point(cx - 3, cy + 3),
            fitz.Point(ix0, cy), fitz.Point(cx - 3, cy - 3),
            fitz.Point(cx, iy0)
        ], color=COLOR_BLACK, fill=COLOR_BLACK, width=lw)
        scx = ix1 - 3
        scy = iy0 + 3
        page.draw_circle(fitz.Point(scx, scy), 1.5, color=COLOR_BLACK, fill=COLOR_BLACK)

    elif icon_type == 'globe':
        # Globe / Online store
        r = icon_w / 2
        page.draw_circle(fitz.Point(cx, cy), r, color=COLOR_BLACK, fill=None, width=lw)
        page.draw_line(fitz.Point(ix0, cy), fitz.Point(ix1, cy), color=COLOR_BLACK, width=lw * 0.7)
        page.draw_line(fitz.Point(cx, iy0), fitz.Point(cx, iy1), color=COLOR_BLACK, width=lw * 0.7)
        page.draw_circle(fitz.Point(cx - r*0.3, cy), r*1.04, color=COLOR_BLACK, fill=None, width=lw * 0.4)
        page.draw_circle(fitz.Point(cx + r*0.3, cy), r*1.04, color=COLOR_BLACK, fill=None, width=lw * 0.4)


# ══════════════════════════════════════════════════════════════════════════
# Main overlay function
# ══════════════════════════════════════════════════════════════════════════

def add_store_strip(
    pdf_bytes:  bytes,
    store_link: str,
    store_name: str = DEFAULT_STORE_NAME,
    follow_text: str = DEFAULT_FOLLOW_TEXT,
    convert_4x6: bool = False,
    shop_icon: str = 'shop',
) -> bytes:
    """
    Stamps a store branding strip into the bottom free space of the PDF.
    Scales the original label content down to guarantee zero layout overlaps.
    """
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    new_doc = fitz.open()
    
    # Pre-generate QR code bytes once for maximum performance across multi-page labels
    qr_png_bytes = _make_qr_png(store_link, size_px=300)
    
    for page in doc:
        # Determine target dimensions
        if convert_4x6:
            W, H = 288, 432
        else:
            W, H = page.rect.width, page.rect.height
            
        new_page = new_doc.new_page(width=W, height=H)
        
        # ── Collision Guard: Scale original label content down to fit above the strip ──
        # Branding strip takes STRIP_HEIGHT + STRIP_MARGIN = 70 points
        label_rect = fitz.Rect(0, 0, W, H - STRIP_HEIGHT - STRIP_MARGIN)
        new_page.show_pdf_page(label_rect, doc, page.number, keep_proportion=True)
 
        # ── Strip boundary ────────────────────────────────────────────────────
        sx0 = STRIP_MARGIN
        sy0 = H - STRIP_HEIGHT - STRIP_MARGIN
        sx1 = W - STRIP_MARGIN
        sy1 = H - STRIP_MARGIN
        strip   = fitz.Rect(sx0, sy0, sx1, sy1)
        strip_h = sy1 - sy0
        inner   = 4   # inner padding
 
        # Rounded white background + black border
        new_page.draw_rect(strip, color=COLOR_BLACK, fill=COLOR_WHITE,
                           width=BORDER_WIDTH, radius=RADIUS)
 
        # ── Column split: 55% left (icon+name)  |  45% right (QR+text) ───────
        total_w  = sx1 - sx0
        left_w   = total_w * 0.55
        right_x0 = sx0 + left_w
        right_x1 = sx1
 
        # Vertical divider
        new_page.draw_line(fitz.Point(right_x0, sy0 + inner),
                           fitz.Point(right_x0, sy1 - inner),
                           color=COLOR_GREY, width=0.8)
 
        # ══ LEFT: icon  +  store name ════════════════════════════════════════
        icon_size = strip_h - inner * 2
        icon_x0   = sx0 + inner
        icon_y0   = sy0 + inner
        _draw_icon(new_page, fitz.Rect(icon_x0, icon_y0,
                                   icon_x0 + icon_size, icon_y0 + icon_size), shop_icon)
 
        # Store name — to the right of icon, Jakarta Sans Bold, auto-size
        name_x0   = icon_x0 + icon_size + inner
        name_x1   = sx0 + left_w - inner
        avail_w   = name_x1 - name_x0
 
        fs = 18
        while fs > 8:
            if _text_width(store_name, fs, bold=True) <= avail_w:
                break
            fs -= 1
 
        tw     = _text_width(store_name, fs, bold=True)
        name_x = (name_x0 + name_x1) / 2 - tw / 2          # horizontally centred
        name_y = (sy0 + sy1) / 2 + fs * 0.35                # vertically centred
 
        _insert(new_page, fitz.Point(name_x, name_y), store_name, fs, bold=True)
 
        # Underline
        new_page.draw_line(fitz.Point(name_x, name_y + 3),
                       fitz.Point(name_x + tw, name_y + 3),
                       color=COLOR_BLACK, width=1.2)
 
        # ══ RIGHT: QR code  +  "Follow our shop" text ════════════════════════
        qr_pad  = 2
        qr_size = strip_h - qr_pad * 2   # fills the full height
 
        qr_x    = right_x0 + qr_pad
        qr_y    = sy0 + qr_pad
        qr_rect = fitz.Rect(qr_x, qr_y, qr_x + qr_size, qr_y + qr_size)
        new_page.insert_image(qr_rect, stream=qr_png_bytes)
 
        # Follow text — RIGHT of QR, vertically centred, Jakarta Sans Bold (size 11 to avoid clashing)
        cap_fs    = 11.0
        text_x    = qr_x + qr_size + 3
        cap_lines = [l.strip() for l in follow_text.splitlines() if l.strip()]
        total_h   = len(cap_lines) * (cap_fs + 3)
        ty_start  = (sy0 + sy1) / 2 - total_h / 2 + cap_fs
 
        for i, line in enumerate(cap_lines):
            # Use bold for the follow text
            fp = _font_path(bold=True, semi=False)
            if fp:
                try:
                    new_page.insert_text(
                        fitz.Point(text_x, ty_start + i * (cap_fs + 3)),
                        line,
                        fontfile=fp,
                        fontname='jakarta-b',
                        fontsize=cap_fs,
                        color=COLOR_BLACK,
                    )
                    continue
                except Exception:
                    pass
            _insert(new_page, fitz.Point(text_x, ty_start + i * (cap_fs + 3)),
                    line, cap_fs, bold=True)
 
    return new_doc.tobytes()
