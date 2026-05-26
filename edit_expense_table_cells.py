"""
Edit expense table image: change serial 8 -> 7, 交通费 -> 活动费 in that row.
Uses horizontal line detection + template matching in the first column.
"""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

WORK = Path(r"C:\Users\kewang\OneDrive - Nokia\Projects\Cursor\AnaysisOnJiraData")
SRC = WORK / "expense_table_edit.png"
OUT = WORK / "expense_table_edited.png"

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
]


def pick_font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_CANDIDATES:
        if Path(p).is_file():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def cluster_ys(ys: list[int], tol: int = 8) -> list[int]:
    ys = sorted(ys)
    if not ys:
        return []
    out = [ys[0]]
    for y in ys[1:]:
        if y - out[-1] > tol:
            out.append(y)
        else:
            out[-1] = (out[-1] + y) // 2
    return out


def horizontal_line_ys(gray: np.ndarray) -> list[int]:
    h, w = gray.shape
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blur, 40, 120)
    min_len = max(w // 3, 200)
    lines = cv2.HoughLinesP(
        edges, 1, math.pi / 180, threshold=max(80, w // 8), minLineLength=min_len, maxLineGap=15
    )
    ys: list[int] = []
    if lines is None:
        return ys
    for ln in lines[:, 0, :]:
        x1, y1, x2, y2 = ln
        if abs(y2 - y1) <= 2 and abs(x2 - x1) >= min_len * 0.85:
            ys.append(int(round((y1 + y2) / 2)))
    return cluster_ys(ys, tol=10)


def row_bands_from_lines(ys: list[int], h: int) -> list[tuple[int, int]]:
    ys = sorted(set(ys))
    if len(ys) < 3:
        return []
    bands: list[tuple[int, int]] = []
    for i in range(len(ys) - 1):
        y0, y1 = ys[i], ys[i + 1]
        if y1 - y0 > 12:
            bands.append((y0 + 2, y1 - 2))
    return bands


def render_gray_template(ch: str, size: int) -> np.ndarray:
    font = pick_font(size)
    pad = size * 3
    im = Image.new("L", (pad, pad), 255)
    dr = ImageDraw.Draw(im)
    dr.text((pad // 6, pad // 6), ch, font=font, fill=0)
    bb = im.getbbox()
    if not bb:
        return np.zeros((10, 10), np.uint8)
    im = im.crop(bb)
    return np.array(im, dtype=np.uint8)


def best_match_score(patch: np.ndarray, tmpl: np.ndarray) -> float:
    ph, pw = patch.shape
    th, tw = tmpl.shape
    if ph < th + 2 or pw < tw + 2:
        return -1.0
    res = cv2.matchTemplate(patch, tmpl, cv2.TM_CCOEFF_NORMED)
    _, maxv, _, _ = cv2.minMaxLoc(res)
    return float(maxv)


def main() -> None:
    img = cv2.imread(str(SRC))
    if img is None:
        raise SystemExit(f"Missing {SRC}")
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    line_ys = horizontal_line_ys(gray)
    bands = row_bands_from_lines(line_ys, h)

    # Fallback: equal bands in central table area if Hough fails
    if len(bands) < 4:
        y0, y1 = int(h * 0.18), int(h * 0.92)
        nrows = 8
        step = (y1 - y0) / nrows
        bands = [(int(y0 + i * step), int(y0 + (i + 1) * step)) for i in range(nrows)]

    # Column x-ranges (fractions of width). Category column must fully cover "交通费".
    x_sep01 = int(w * 0.10)
    x_sep12 = int(w * 0.30)
    x0_c0, x1_c0 = int(w * 0.02), x_sep01 - 2
    x0_c1, x1_c1 = x_sep01 + 2, int(w * 0.42)

    tmpl8 = render_gray_template("8", size=max(22, int(h * 0.045)))

    target_row: int | None = None
    best_sc = -1.0
    for i, (ya, yb) in enumerate(bands):
        patch = gray[ya:yb, x0_c0:x1_c0]
        sc = best_match_score(patch, tmpl8)
        if sc > best_sc:
            best_sc = sc
            target_row = i

    if target_row is None or best_sc < 0.25:
        # Last resort: assume second-to-last data band before bottom band
        target_row = max(0, len(bands) - 2)

    ya, yb = bands[target_row]
    pad_y = max(3, (yb - ya) // 12)
    by0, by1 = max(0, ya + pad_y), min(h, yb - pad_y)

    # --- Column 0: clear interior (keep grid lines), draw 7 ---
    bx0, bx1 = max(0, x0_c0), min(w, x1_c0)
    img[by0:by1, bx0:bx1] = (255, 255, 255)

    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    dr = ImageDraw.Draw(pil)
    font_size = max(20, int((yb - ya) * 0.52))
    font = pick_font(font_size)
    tw, th = dr.textbbox((0, 0), "7", font=font)[2:]
    tx = (bx0 + bx1 - tw) // 2
    ty = (by0 + by1 - th) // 2
    dr.text((tx, ty), "7", fill=(0, 0, 0), font=font)

    # --- Column 1: clear wide interior, draw 活动费 ---
    cx0, cx1 = max(0, x0_c1), min(w, x1_c1)
    np_img = np.array(pil)
    np_img[by0:by1, cx0:cx1] = (255, 255, 255)
    pil = Image.fromarray(np_img)
    dr = ImageDraw.Draw(pil)
    cat = "活动费"
    tw2, th2 = dr.textbbox((0, 0), cat, font=font)[2:]
    tx2 = cx0 + max(2, (cx1 - cx0 - tw2) // 2)
    ty2 = (by0 + by1 - th2) // 2
    dr.text((tx2, ty2), cat, fill=(0, 0, 0), font=font)

    out_bgr = cv2.cvtColor(np.array(pil.convert("RGB")), cv2.COLOR_RGB2BGR)
    # Restore vertical grid lines through this row (white fill erased borders)
    black = (0, 0, 0)
    t = 2
    cv2.line(out_bgr, (x_sep01, ya), (x_sep01, yb), black, t)
    cv2.line(out_bgr, (x_sep12, ya), (x_sep12, yb), black, t)
    cv2.imwrite(str(OUT), out_bgr)
    print("Saved:", OUT, "target_row", target_row, "match8", round(best_sc, 3), "n_bands", len(bands))


if __name__ == "__main__":
    main()
