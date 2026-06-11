"""Generate placeholder Play Store / iOS App Store assets for A1 Field Pro.
Brand palette: Blue #1D4ED8, Deep navy #0F172A, Red #DC2626, White.

Outputs (per Expo + Play Store specs):
  /app/mobile/assets/icon.png           1024 x 1024  (App Store icon)
  /app/mobile/assets/adaptive-icon.png  1024 x 1024  (Android adaptive — foreground; safe area 432px diameter)
  /app/mobile/assets/splash.png         1284 x 2778  (iPhone 14 Pro Max — Expo scales for all)
  /app/mobile/assets/favicon.png        48 x 48
  /app/mobile/assets/play-feature.png   1024 x 500   (Play Store feature graphic)
"""
from __future__ import annotations
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = "/app/mobile/assets"
os.makedirs(OUT, exist_ok=True)

BLUE = (29, 78, 216)           # #1D4ED8
DARK = (15, 23, 42)            # #0F172A
RED  = (220, 38, 38)           # #DC2626
WHITE = (255, 255, 255)


def _find_bold_font(size: int) -> ImageFont.FreeTypeFont:
    """Try a list of common bold fonts on the container, fallback to default."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVu-Sans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _radial_gradient(size, inner, outer):
    """Cheap radial gradient by drawing concentric circles."""
    img = Image.new("RGB", (size, size), outer)
    d = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    for r in range(size // 2, 0, -2):
        t = r / (size / 2)
        color = tuple(int(outer[i] * t + inner[i] * (1 - t)) for i in range(3))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    return img


def _draw_logo_mark(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int):
    """Draw a stylised 'A1' wordmark with a red bolt accent."""
    font = _find_bold_font(int(size * 0.55))
    text = "A1"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw / 2 - bbox[0], cy - th / 2 - bbox[1] - int(size * 0.04)), text, fill=WHITE, font=font)

    # Red lightning bolt accent (top-right)
    bolt_w = int(size * 0.22)
    bx, by = cx + int(size * 0.18), cy - int(size * 0.32)
    pts = [
        (bx, by),
        (bx + bolt_w // 2, by + bolt_w),
        (bx + bolt_w // 3, by + bolt_w),
        (bx + 2 * bolt_w // 3, by + bolt_w * 2),
        (bx - bolt_w // 4, by + bolt_w // 2),
        (bx + bolt_w // 6, by + bolt_w // 2),
    ]
    draw.polygon(pts, fill=RED)


def build_icon(out_path: str, dim: int = 1024, rounded: bool = False, safe_pct: float = 1.0):
    """Square icon with brand gradient + 'A1' wordmark.
    `safe_pct` < 1.0 inset content (used for adaptive-icon — Android masks circle/squircle)."""
    img = _radial_gradient(dim, BLUE, DARK)
    d = ImageDraw.Draw(img)
    inner = int(dim * safe_pct)
    cx, cy = dim // 2, dim // 2
    _draw_logo_mark(d, cx, cy, inner)
    if rounded:
        # iOS-style rounded square mask (~22% radius)
        mask = Image.new("L", (dim, dim), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, dim, dim], radius=int(dim * 0.22), fill=255)
        out = Image.new("RGBA", (dim, dim), (0, 0, 0, 0))
        out.paste(img, (0, 0), mask)
        out.save(out_path)
    else:
        img.save(out_path)


def build_splash(out_path: str, w: int = 1284, h: int = 2778):
    img = Image.new("RGB", (w, h), DARK)
    d = ImageDraw.Draw(img)

    # subtle gradient overlay
    for y in range(h):
        t = y / h
        col = tuple(int(DARK[i] * (1 - t) + BLUE[i] * t * 0.35) for i in range(3))
        d.line([(0, y), (w, y)], fill=col)

    # Center logo mark
    cx, cy = w // 2, int(h * 0.42)
    mark = int(min(w, h) * 0.35)
    d.ellipse([cx - mark // 2, cy - mark // 2, cx + mark // 2, cy + mark // 2], fill=BLUE)
    _draw_logo_mark(d, cx, cy, mark)

    # Wordmark below
    title_font = _find_bold_font(int(w * 0.075))
    title = "A1 Field Pro"
    bbox = d.textbbox((0, 0), title, font=title_font)
    tw = bbox[2] - bbox[0]
    d.text((cx - tw / 2 - bbox[0], cy + mark // 2 + 60), title, fill=WHITE, font=title_font)

    tagline_font = _find_bold_font(int(w * 0.032))
    tagline = "Field Service Management"
    bbox = d.textbbox((0, 0), tagline, font=tagline_font)
    tw = bbox[2] - bbox[0]
    d.text((cx - tw / 2 - bbox[0], cy + mark // 2 + 60 + int(w * 0.09)), tagline, fill=(148, 163, 184), font=tagline_font)

    img.save(out_path)


def build_feature_graphic(out_path: str, w: int = 1024, h: int = 500):
    """Play Store feature graphic banner."""
    img = Image.new("RGB", (w, h), DARK)
    d = ImageDraw.Draw(img)

    # Diagonal sweep
    for x in range(w):
        t = x / w
        col = tuple(int(DARK[i] * (1 - t) + BLUE[i] * t) for i in range(3))
        d.line([(x, 0), (x, h)], fill=col)

    # Logo circle on the left
    cx, cy = int(w * 0.22), h // 2
    mark = int(h * 0.55)
    d.ellipse([cx - mark // 2, cy - mark // 2, cx + mark // 2, cy + mark // 2], fill=WHITE)
    bf = _find_bold_font(int(mark * 0.55))
    bbox = d.textbbox((0, 0), "A1", font=bf)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text((cx - tw / 2 - bbox[0], cy - th / 2 - bbox[1]), "A1", fill=BLUE, font=bf)

    # Wordmark + tag right
    title_font = _find_bold_font(int(h * 0.16))
    d.text((int(w * 0.40), int(h * 0.30)), "A1 Field Pro", fill=WHITE, font=title_font)
    tag_font = _find_bold_font(int(h * 0.07))
    d.text((int(w * 0.40), int(h * 0.55)), "Dispatch · Schedule · Get Paid", fill=(186, 214, 255), font=tag_font)

    img.save(out_path)


if __name__ == "__main__":
    build_icon(os.path.join(OUT, "icon.png"), dim=1024, rounded=False)
    # Adaptive icon foreground: Android masks it (circle/squircle/rounded), so inset content ~70% of canvas
    build_icon(os.path.join(OUT, "adaptive-icon.png"), dim=1024, safe_pct=0.70)
    build_icon(os.path.join(OUT, "favicon.png"), dim=48)
    build_splash(os.path.join(OUT, "splash.png"), w=1284, h=2778)
    build_feature_graphic(os.path.join(OUT, "play-feature.png"))
    print("Generated:")
    for n in ("icon.png", "adaptive-icon.png", "favicon.png", "splash.png", "play-feature.png"):
        p = os.path.join(OUT, n)
        with Image.open(p) as im:
            print(f"  {n:24s}  {im.size[0]}x{im.size[1]}  {os.path.getsize(p)//1024} KB")
