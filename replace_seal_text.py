"""
Replace curved company name on red seal: wipe bright strokes except top
registration arc and left-side serial arc, then draw new text along bottom/right inner arc.
"""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = Path(r"C:\Users\kewang\OneDrive - Nokia\Projects\Cursor\AnaysisOnJiraData")
SRC = BASE / "expense_seal_source.png"
OUT = BASE / "expense_seal_replaced.png"

NEW_TEXT = "安吉报福云儿田田民宿"

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
]


def pick_font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_CANDIDATES:
        if Path(p).is_file():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def main() -> None:
    img_bgr = cv2.imread(str(SRC))
    if img_bgr is None:
        raise SystemExit(f"Missing {SRC}")

    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    m1 = cv2.inRange(hsv, (0, 40, 40), (12, 255, 255))
    m2 = cv2.inRange(hsv, (168, 40, 40), (180, 255, 255))
    red = cv2.bitwise_or(m1, m2)
    red = cv2.morphologyEx(red, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=2)
    red_b = red > 0

    cnts, _ = cv2.findContours(red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        raise SystemExit("No red seal found")
    best = max(cnts, key=cv2.contourArea)
    M = cv2.moments(best)
    cx = float(M["m10"] / M["m00"])
    cy = float(M["m01"] / M["m00"])
    (_, _), R = cv2.minEnclosingCircle(best)

    mean_bgr = cv2.mean(img_bgr, mask=red)[:3]
    mean_rgb = (int(mean_bgr[2]), int(mean_bgr[1]), int(mean_bgr[0]))

    yy, xx = np.ogrid[:h, :w]
    dx = xx.astype(np.float64) - cx
    dy = yy.astype(np.float64) - cy
    dist = np.sqrt(dx * dx + dy * dy)
    ang = np.arctan2(dy, dx)

    inner = (dist > R * 0.30) & (dist < R * 0.94) & red_b
    bright = gray > 160
    text_stroke = inner & bright

    star_excl = dist < R * 0.28
    # Top registration numbers (inner top arc)
    top_excl = (yy < cy - 0.085 * R) & (np.abs(ang + math.pi / 2) < 1.05)
    # Left-side vertical serial (inner left arc)
    left_excl = (xx < cx) & (np.abs(ang) > 2.12) & (yy < cy + 0.17 * R)

    wipe = text_stroke & ~star_excl & ~top_excl & ~left_excl

    wipe_u8 = (wipe.astype(np.uint8) * 255)
    wipe_u8 = cv2.dilate(wipe_u8, np.ones((4, 4), np.uint8), iterations=2)
    wipe = wipe_u8 > 0

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    arr = img_rgb.copy()
    arr[wipe] = mean_rgb

    pil = Image.fromarray(arr).convert("RGBA")
    font_size = max(17, int(R * 0.175))
    font = pick_font(font_size)
    text_color = (255, 255, 255, 255)

    n = len(NEW_TEXT)
    r_text = R * 0.67
    # Long arc along bottom + right inner edge (10 chars)
    draw_a0 = math.radians(-52)
    draw_a1 = math.radians(162)

    for i, ch in enumerate(NEW_TEXT):
        t = draw_a0 + (draw_a1 - draw_a0) * (i / max(n - 1, 1))
        px = cx + r_text * math.cos(t)
        py = cy + r_text * math.sin(t)
        rot = math.degrees(t) - 90.0

        pad = int(font_size * 2.5)
        ch_img = Image.new("RGBA", (pad, pad), (0, 0, 0, 0))
        cd = ImageDraw.Draw(ch_img)
        cd.text((pad // 4, pad // 6), ch, font=font, fill=text_color)
        bb = ch_img.getbbox()
        if bb:
            ch_img = ch_img.crop(bb)
        ch_img = ch_img.rotate(
            rot, expand=True, resample=Image.Resampling.BICUBIC, fillcolor=(0, 0, 0, 0)
        )
        tw, th = ch_img.size
        pil.paste(ch_img, (int(px - tw / 2), int(py - th / 2)), ch_img)

    pil.convert("RGB").save(OUT, format="PNG", optimize=True)
    print("Saved:", OUT)


if __name__ == "__main__":
    main()
