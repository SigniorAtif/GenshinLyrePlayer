"""ROI management: scales bounding boxes to video resolution and extracts intensities."""

from __future__ import annotations

import logging

import cv2
import numpy as np

from vision_parser.config.schema import InstrumentConfig, ROIBox

logger = logging.getLogger(__name__)


class ROIManager:
    """Scales ROI boxes to the actual video resolution and extracts mean intensities.

    Coordinates from the config JSON are defined at a reference resolution.
    At construction time this class computes scaled integer slice tuples for
    all 21 ROIs once; every subsequent intensity extraction is 21 np.mean() calls
    with no Python-level coordinate math.

    Args:
        cfg: InstrumentConfig whose rois are at cfg.resolution pixel space.
        video_w: Actual video frame width in pixels.
        video_h: Actual video frame height in pixels.
    """

    def __init__(self, cfg: InstrumentConfig, video_w: int, video_h: int) -> None:
        scaled_cfg = cfg.scale_to(video_w, video_h)
        self._boxes: list[ROIBox] = scaled_cfg.rois
        self._panel_crop = scaled_cfg.panel_crop
        # Pre-compute slice objects for zero-overhead crop in the hot loop.
        self._slices: list[tuple[slice, slice]] = [
            (slice(b.y, b.y + b.h), slice(b.x, b.x + b.w))
            for b in self._boxes
        ]
        logger.debug(
            "ROIManager initialized — %d ROIs scaled from %dx%d to %dx%d",
            len(self._boxes),
            cfg.resolution.width,
            cfg.resolution.height,
            video_w,
            video_h,
        )

    @property
    def roi_boxes(self) -> list[ROIBox]:
        """Scaled ROI boxes in key-definition order."""
        return self._boxes

    def extract_intensities(self, gray: np.ndarray) -> dict[str, float]:
        """Compute mean pixel intensity for each ROI.

        Args:
            gray: Preprocessed grayscale frame, shape (H, W), dtype uint8.

        Returns:
            Dict mapping key name → mean intensity (float in [0.0, 255.0]).
        """
        return {
            box.key: float(np.mean(gray[row_sl, col_sl]))
            for box, (row_sl, col_sl) in zip(self._boxes, self._slices)
        }

    def debug_overlay_cropped(self, bgr: np.ndarray) -> np.ndarray:
        """Return only the panel region with ROI boxes drawn on it.

        Crops to the panel first so the debugger window shows only the keys —
        much easier to inspect alignment than overlaying on the full frame.

        When ``panel_crop`` is set, ROI box coordinates are already panel-
        relative so no offset is applied.  When ``panel_crop`` is ``None``
        (full-frame coords), the crop is computed from the bounding box of all
        ROI boxes.

        Args:
            bgr: Full-resolution BGR frame.

        Returns:
            Cropped BGR image with green rectangles and key labels.
        """
        if self._panel_crop:
            c = self._panel_crop
            out = bgr[c.y : c.y + c.h, c.x : c.x + c.w].copy()
            ox = oy = 0   # boxes are already panel-relative
        else:
            # Full-frame ROI coords → compute bounding box + margin for crop.
            margin = 20
            all_x = [b.x for b in self._boxes]
            all_y = [b.y for b in self._boxes]
            crop_x = max(0, min(all_x) - margin)
            crop_y = max(0, min(all_y) - margin)
            crop_x2 = min(bgr.shape[1], max(b.x + b.w for b in self._boxes) + margin)
            crop_y2 = min(bgr.shape[0], max(b.y + b.h for b in self._boxes) + margin)
            out = bgr[crop_y:crop_y2, crop_x:crop_x2].copy()
            ox = -crop_x
            oy = -crop_y

        for box in self._boxes:
            x0, y0 = box.x + ox, box.y + oy
            cv2.rectangle(out, (x0, y0), (x0 + box.w, y0 + box.h), (0, 255, 0), 1)
            cv2.putText(
                out, box.key, (x0 + 2, y0 + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1, cv2.LINE_AA,
            )
        return out
