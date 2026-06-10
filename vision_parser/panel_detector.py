"""Auto-detects the Genshin Lyre instrument panel in a video frame.

Strategy
--------
1. Threshold the grayscale frame at several brightness levels to find
   the white/cream key-button blobs.
2. Filter contours by circularity and size; keep only those in the lower
   70 % of the frame (Lyre panel is always below the character).
3. Cluster x-coordinates into 7 columns (k-means, k=7) and y-coordinates
   into 3 rows (k-means, k=3) across ALL detected circles — so a single
   missing or darker key doesn't break the column/row identification.
4. Use the cluster-centre grid for every key position; no detected circle
   needed for a cell (handles keys that are below any brightness threshold).
5. Return a PanelCrop + 21 ROIBox objects relative to that crop.

Why not HoughCircles?
---------------------
HoughCircles requires precise tuning per video.  At 848x544 it finds either
13 circles (param2=22) or 95 circles of noise (param2=11) — no sweet spot.
The contour approach finds the 20/21 keys cleanly at a single threshold.
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

from vision_parser.config.schema import PanelCrop, ROIBox

logger = logging.getLogger(__name__)

# Key layout: row 0 = top (high pitch), row 2 = bottom (low pitch).
_KEY_GRID: list[list[str]] = [
    ["Q", "W", "E", "R", "T", "Y", "U"],
    ["A", "S", "D", "F", "G", "H", "J"],
    ["Z", "X", "C", "V", "B", "N", "M"],
]

_N_ROWS = 3
_N_COLS = 7
_MIN_DETECTED = 15          # accept if at least this many circles found
_MIN_CIRCULARITY = 0.50     # discard elongated shapes
_AREA_TOLERANCE = 0.45      # keep circles within ±45 % of median area
_SPACING_TOLERANCE = 0.35   # accept grid if spacing CV ≤ 35 %


def detect_panel(
    bgr: np.ndarray,
) -> tuple[PanelCrop, list[ROIBox]] | tuple[None, None]:
    """Locate the Lyre panel in a full BGR video frame.

    Tries several brightness thresholds until a valid 3×7 key grid is found.

    Args:
        bgr: Full-resolution BGR frame from the video.

    Returns:
        ``(panel_crop, roi_boxes)`` — panel_crop in full-frame coords,
        roi_boxes relative to panel_crop origin — or ``(None, None)``.
    """
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # Radius bounds scale with frame height. Keys are ~2–4 % of frame height.
    r_min = max(5, int(h * 0.018))
    r_max = max(r_min + 5, int(h * 0.060))
    y_min = int(h * 0.28)    # Lyre panel is in the lower ~72 % of the frame

    for threshold in (190, 185, 180, 175, 200, 210, 170):
        circles = _find_circles(gray, threshold, r_min, r_max, y_min)
        if circles is None or len(circles) < _MIN_DETECTED:
            continue
        result = _fit_grid(circles, w, h, r_min, r_max)
        if result[0] is not None:
            logger.info(
                "Panel detected (thresh=%d, %d/%d circles used)",
                threshold, len(circles), _N_ROWS * _N_COLS,
            )
            return result

    logger.debug("detect_panel: no valid 3×7 grid found in any threshold pass")
    return None, None


# ─── Contour-based circle finder ─────────────────────────────────────────────

def _find_circles(
    gray: np.ndarray,
    threshold: int,
    r_min: int,
    r_max: int,
    y_min: int,
) -> np.ndarray | None:
    """Return (N, 3) array of (cx, cy, r) for bright circular blobs.

    Filters by circularity, size, vertical position, and area similarity.
    Returns ``None`` if fewer than ``_MIN_DETECTED`` candidates survive.
    """
    _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates: list[tuple[float, float, float, float]] = []  # cx, cy, r, area
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < np.pi * r_min ** 2 * 0.5:
            continue
        peri = cv2.arcLength(cnt, True)
        if peri == 0:
            continue
        circularity = 4.0 * np.pi * area / (peri ** 2)
        if circularity < _MIN_CIRCULARITY:
            continue
        (cx, cy), r = cv2.minEnclosingCircle(cnt)
        if cy < y_min or not (r_min <= r <= r_max):
            continue
        candidates.append((cx, cy, r, area))

    if len(candidates) < _MIN_DETECTED:
        return None

    # Keep only the "area cluster" — the Lyre keys are all the same size.
    areas = np.array([c[3] for c in candidates])
    # Median of the largest 21 (or all if fewer) — that's the key cluster.
    top_n = min(21, len(areas))
    median_area = float(np.median(np.sort(areas)[-top_n:]))
    filtered = [
        c for c in candidates
        if abs(c[3] - median_area) / (median_area + 1e-6) <= _AREA_TOLERANCE
    ]

    if len(filtered) < _MIN_DETECTED:
        return None

    return np.array([(int(c[0]), int(c[1]), int(c[2])) for c in filtered], dtype=int)


# ─── Grid fitting ─────────────────────────────────────────────────────────────

def _fit_grid(
    circles: np.ndarray,
    frame_w: int,
    frame_h: int,
    r_min: int,
    r_max: int,
) -> tuple[PanelCrop, list[ROIBox]] | tuple[None, None]:
    """Fit a 3-row × 7-col grid to the detected circles using k-means.

    Clusters y-coords into 3 rows and ALL x-coords into 7 columns
    (so a missing key in one row doesn't break that column's detection).
    Every grid cell's centre is the k-means centroid — inferred if no
    circle was found there.
    """
    # ── 1. Cluster rows ───────────────────────────────────────────────────
    y_pts = circles[:, 1].astype(np.float32).reshape(-1, 1)
    if len(np.unique(y_pts)) < _N_ROWS:
        return None, None

    _, row_labels, row_ctrs = cv2.kmeans(
        y_pts, _N_ROWS, None,
        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 1.0),
        5, cv2.KMEANS_PP_CENTERS,
    )
    row_y = sorted(row_ctrs.flatten().tolist())   # top → bottom

    # ── 2. Cluster columns (ALL circles, not per-row) ─────────────────────
    x_pts = circles[:, 0].astype(np.float32).reshape(-1, 1)
    if len(np.unique(x_pts)) < _N_COLS:
        return None, None

    _, col_labels, col_ctrs = cv2.kmeans(
        x_pts, _N_COLS, None,
        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 1.0),
        5, cv2.KMEANS_PP_CENTERS,
    )
    col_x = sorted(col_ctrs.flatten().tolist())   # left → right

    # ── 3. Validate spacing uniformity ───────────────────────────────────
    row_gaps = np.diff(row_y)
    col_gaps = np.diff(col_x)
    for gaps, name in ((row_gaps, "row"), (col_gaps, "col")):
        if gaps.mean() == 0:
            return None, None
        cv = float(np.std(gaps) / gaps.mean())
        if cv > _SPACING_TOLERANCE:
            logger.debug("Rejecting: %s spacing CV=%.2f > %.2f", name, cv, _SPACING_TOLERANCE)
            return None, None

    # ── 4. Build panel crop ───────────────────────────────────────────────
    med_r = int(np.median(circles[:, 2]))
    roi_half = max(3, int(med_r * 0.90))
    margin = int(med_r * 1.6)

    px = max(0, int(col_x[0])  - margin)
    py = max(0, int(row_y[0])  - margin)
    pr = min(frame_w, int(col_x[-1]) + margin + med_r)
    pb = min(frame_h, int(row_y[-1]) + margin + med_r)
    panel = PanelCrop(x=px, y=py, w=pr - px, h=pb - py)

    # ── 5. ROI boxes at each grid position (panel-relative) ───────────────
    roi_boxes: list[ROIBox] = []
    for row_i, key_row in enumerate(_KEY_GRID):
        for col_i, key_name in enumerate(key_row):
            cx = int(round(col_x[col_i])) - px
            cy = int(round(row_y[row_i])) - py
            roi_boxes.append(ROIBox(
                key=key_name,
                x=max(0, cx - roi_half),
                y=max(0, cy - roi_half),
                w=roi_half * 2,
                h=roi_half * 2,
            ))

    logger.debug(
        "Grid: rows y=%s  cols x=%s  med_r=%d  roi=%d",
        [round(v) for v in row_y], [round(v) for v in col_x], med_r, roi_half * 2,
    )
    return panel, roi_boxes
