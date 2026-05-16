"""Replace background with white: GrabCut + edge artifact cleanup."""
from __future__ import annotations

import cv2
import numpy as np

BASE = r"C:\Users\kewang\OneDrive - Nokia\Projects\Cursor\AnaysisOnJiraData"
INPUT = rf"{BASE}\source_portrait.png"
OUTPUT_WORKSPACE = rf"{BASE}\portrait_white_background.png"


def corner_mean_bgr(img: np.ndarray, s: int = 24) -> np.ndarray:
    h, w, _ = img.shape
    s = min(s, h // 5, w // 5)
    pts = np.vstack(
        [
            img[:s, :s].reshape(-1, 3),
            img[:s, -s:].reshape(-1, 3),
            img[-s:, :s].reshape(-1, 3),
            img[-s:, -s:].reshape(-1, 3),
        ]
    )
    return np.mean(pts, axis=0)


def main() -> None:
    img = cv2.imread(INPUT, cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"Could not read {INPUT}")
    h, w = img.shape[:2]

    mask_gc = np.zeros((h, w), np.uint8)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)

    x0 = int(w * 0.11)
    y0 = int(h * 0.04)
    rw = int(w * 0.78)
    rh = int(h * 0.90)
    rect = (x0, y0, rw, rh)

    cv2.grabCut(img, mask_gc, rect, bgd, fgd, 8, cv2.GC_INIT_WITH_RECT)
    cv2.grabCut(img, mask_gc, None, bgd, fgd, 5, cv2.GC_EVAL)

    bin_mask = np.where((mask_gc == cv2.GC_BGD) | (mask_gc == cv2.GC_PR_BGD), 0.0, 1.0).astype(
        np.float32
    )

    km = (bin_mask * 255).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    km = cv2.dilate(km, kernel, iterations=1)
    alpha_gc = km.astype(np.float32) / 255.0
    alpha = alpha_gc.copy()

    # --- Remove hinges / trim that GrabCut kept as FG near the frame ---
    yy = np.arange(h, dtype=np.float32)[:, np.newaxis]
    xx = np.arange(w, dtype=np.float32)[np.newaxis, :]
    dist_edge = np.minimum(np.minimum(yy, (h - 1) - yy), np.minimum(xx, (w - 1) - xx))
    near_edge = dist_edge < 36.0

    bg_ref = corner_mean_bgr(img)
    dist_bgr = np.linalg.norm(img.astype(np.float32) - bg_ref, axis=2)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    h_ch, s_ch, v_ch = cv2.split(hsv)

    door_like = (dist_bgr < 52.0) | ((s_ch < 55.0) & (v_ch > 105.0))
    brass_trim = (s_ch > 22.0) & (h_ch > 7.0) & (h_ch < 40.0) & (v_ch > 65.0)

    # Flat painted door / cream wall (used to avoid deleting real clothing)
    wall_paint = (dist_bgr < 46.0) & (s_ch < 38.0) & (gray > 185.0)

    junk_fg = (alpha > 0.05) & near_edge & (door_like | brass_trim)
    alpha[junk_fg] = 0.0

    # Never treat obvious torso/clothing as mistaken hinge blobs (protects collars & grey shirts)
    torso_guard = (yy > (h * 0.30)) & (
        ~wall_paint | (dist_bgr > 18.0) | (s_ch > 6.0) | (gray < 246.0)
    )

    # Drop small mistaken-foreground blobs (hinges, door frame chips) anywhere in frame
    mistaken = (alpha > 0.06) & (
        (dist_bgr < 58.0) | brass_trim | ((s_ch < 62.0) & (v_ch > 92.0))
    )
    mistaken &= ~torso_guard
    mistaken_u8 = mistaken.astype(np.uint8)
    n_lab, labels, stats, _ = cv2.connectedComponentsWithStats(mistaken_u8, connectivity=8)
    max_small = max(6000, int(h * w * 0.012))
    for i in range(1, n_lab):
        if stats[i, cv2.CC_STAT_AREA] <= max_small:
            alpha[labels == i] = 0.0

    # Bottom corners: only strip pixels that still look like wall — avoids bleaching shirt hems
    bottom_strip = yy > (h * 0.68)
    stray = (
        (alpha > 0.04)
        & bottom_strip
        & (dist_edge < 98.0)
        & wall_paint
        & (dist_bgr < 52.0)
        & (s_ch < 42.0)
    )
    alpha[stray] = 0.0

    # Refill shirt/collar: GrabCut + cleanup often erase clothing (holes → white). Restore FG where
    # the pixel cannot be flat door paint, or where cleanup punched a hole through real fabric.
    torso = yy >= (h * 0.30)
    not_wall = ~wall_paint | (dist_bgr > 32.0) | (s_ch > 12.0) | (gray < 232.0)
    trim_at_rim = near_edge & brass_trim & (dist_edge < 48.0) & (dist_bgr < 62.0)
    clothing_like = torso & not_wall & ~trim_at_rim

    punch_out = clothing_like & (alpha_gc > 0.75) & (alpha < 0.55)
    alpha = np.where(punch_out, np.maximum(alpha, alpha_gc), alpha)

    force_full = clothing_like & ((dist_bgr > 22.0) | (s_ch > 7.5) | (gray < 244.0))
    alpha = np.where(force_full, np.maximum(alpha, 1.0), alpha)

    # Feather only the upper silhouette (hair / face). No blur on torso — blur mixes in white and
    # makes shirts look bleached.
    alpha_sharp = alpha.copy()
    a8 = np.clip(alpha_sharp * 255.0, 0, 255).astype(np.uint8)
    a_blur = cv2.GaussianBlur(a8, (5, 5), 0).astype(np.float32) / 255.0
    y1, y2 = h * 0.36, h * 0.58
    blur_w = np.clip(((y2 - yy) / (y2 - y1 + 1e-6)), 0.0, 1.0)
    alpha_mixed = a_blur * blur_w + alpha_sharp * (1.0 - blur_w)
    torso_no_feather = yy >= (h * 0.40)
    alpha = np.where(torso_no_feather, alpha_sharp, alpha_mixed)

    white = np.full_like(img, 255, dtype=np.float32)
    comp = img.astype(np.float32) * alpha[..., np.newaxis] + white * (1.0 - alpha[..., np.newaxis])
    out = np.clip(comp, 0, 255).astype(np.uint8)

    cv2.imwrite(OUTPUT_WORKSPACE, out)
    print("Saved:", OUTPUT_WORKSPACE)


if __name__ == "__main__":
    main()
