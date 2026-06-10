"""Top-level orchestrator for the Vision Parser pipeline."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Callable, Optional

import cv2

from vision_parser.chord_grouper import ChordGrouper
from vision_parser.config.schema import InstrumentConfig, ResolutionRef
from vision_parser.edge_detector import EdgeDetector, TriggerEvent
from vision_parser.panel_detector import detect_panel
from vision_parser.preprocessor import Preprocessor
from vision_parser.roi_manager import ROIManager
from vision_parser.timing_engine import TimingEngine
from vision_parser.token_writer import TokenWriter
from vision_parser.video_reader import VideoReader
from shared.logging_config import setup_logging

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).parent.parent / "config" / "roi_profiles"
_DEFAULT_OUTPUT = Path(__file__).parent.parent / "output"


def _auto_config(video_path: str) -> Path:
    """Pick the best-matching ROI profile for the video's resolution.

    Resolution determines the detection channel and threshold set:
    - width ≤ 960 px  →  lyre_848x480.json  (G_minus_R, low thresholds)
    - width  > 960 px  →  lyre_1080p.json    (gray channel, high thresholds)

    The ROI positions inside the chosen config are irrelevant — they are
    always overridden by the auto-panel-detection pass.
    """
    cap = cv2.VideoCapture(video_path)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cap.release()
    if w <= 960:
        chosen = _CONFIG_DIR / "lyre_848x480.json"
        logger.info("Auto-config: %dpx wide -> %s (G_minus_R)", w, chosen.name)
    else:
        chosen = _CONFIG_DIR / "lyre_1080p.json"
        logger.info("Auto-config: %dpx wide -> %s (gray)", w, chosen.name)
    return chosen


class ParserPipeline:
    """Full Vision Parser pipeline: video → .txt sheet music.

    Wires VideoReader → Preprocessor → ROIManager → EdgeDetector
    → TimingEngine → ChordGrouper → TokenWriter in batch mode.

    Batch mode is deliberate: duration assignment requires look-ahead to the
    next event, which is only available after the full trigger list is collected.

    Args:
        cfg: InstrumentConfig loaded from a JSON profile file.
    """

    def __init__(self, cfg: InstrumentConfig) -> None:
        self._cfg = cfg

    def run(
        self,
        video_path: str,
        output_path: str,
        bpm_override: Optional[float] = None,
        intermediate_path: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """Process a video file and write a token .txt file.

        Args:
            video_path: Path to input video (MP4, MKV, AVI, etc.).
            output_path: Path for output .txt token file. Parent directory
                must exist.
            bpm_override: If supplied, overrides the BPM from cfg.timing.bpm.
            intermediate_path: If supplied, saves a JSON file containing the
                raw TriggerEvent list after the CV pass. Useful for debugging
                quantization without re-processing the video.
            progress_callback: Optional callable(frame_index, total_frames)
                invoked every 30 frames for UI progress bars.
        """
        # --- Phase 1: open video ---
        reader = VideoReader(video_path)
        actual_w, actual_h = reader.width, reader.height
        fps = reader.fps  # save before any close/reopen

        # --- Phase 1b: auto-detect panel position from first N frames ---
        # Scans up to 40 raw frames to locate the 3×7 key-button grid.
        # If found, positions override the JSON config so alignment is always
        # exact regardless of resolution, window size, or UI-scale setting.
        active_cfg = self._cfg
        _panel_found = False
        _scan_limit = 40
        for packet in reader.frames():
            panel_crop, roi_boxes = detect_panel(packet.bgr)
            if panel_crop is not None:
                active_cfg = InstrumentConfig(
                    instrument=self._cfg.instrument,
                    resolution=ResolutionRef(width=actual_w, height=actual_h),
                    rois=roi_boxes,
                    detection=self._cfg.detection,
                    timing=self._cfg.timing,
                    panel_crop=panel_crop,
                )
                _panel_found = True
                break
            if packet.frame_index >= _scan_limit:
                break

        if _panel_found:
            logger.info(
                "Panel auto-detected — using dynamic ROI positions "
                "(crop %d×%d at %d,%d)",
                active_cfg.panel_crop.w, active_cfg.panel_crop.h,
                active_cfg.panel_crop.x, active_cfg.panel_crop.y,
            )
            reader.reopen()   # restart from frame 0 for calibration + processing
        else:
            logger.warning(
                "Panel auto-detection failed after %d frames — "
                "falling back to config ROIs (alignment may be off at this resolution)",
                _scan_limit,
            )
            reader.reopen()   # still reopen to reset position

        # --- Phase 1c: initialize pipeline components with chosen config ---
        preprocessor = Preprocessor(active_cfg.detection, panel_crop=active_cfg.panel_crop)
        roi_manager = ROIManager(active_cfg, actual_w, actual_h)
        edge_detector = EdgeDetector(
            active_cfg.detection,
            keys=[box.key for box in roi_manager.roi_boxes],
        )

        total_frames = reader.frame_count  # may be -1 for VFR containers

        # --- Phase 2a: calibrate per-key baselines from leading silent frames ---
        calibrate_n = self._cfg.detection.calibrate_frames
        if calibrate_n > 0:
            calib_samples: list[dict] = []
            for packet in reader.frames():
                calib_samples.append(
                    roi_manager.extract_intensities(preprocessor.process(packet.bgr))
                )
                if len(calib_samples) >= calibrate_n:
                    break
            edge_detector.calibrate(calib_samples)
            logger.info("Calibration done from first %d frames", len(calib_samples))

        # --- Phase 2b: iterate all frames, collect trigger events ---
        all_triggers: list[TriggerEvent] = []

        for packet in reader.frames():
            gray = preprocessor.process(packet.bgr)
            intensities = roi_manager.extract_intensities(gray)
            events = edge_detector.update(intensities, packet.frame_index, packet.timestamp_sec)
            all_triggers.extend(events)

            if progress_callback is not None and packet.frame_index % 30 == 0:
                progress_callback(packet.frame_index, total_frames)

        reader.close()
        logger.info(
            "CV pass complete: %d frames processed, %d triggers collected",
            total_frames,
            len(all_triggers),
        )

        # --- Optional: save intermediate trigger JSON ---
        if intermediate_path is not None:
            payload = {
                "fps": fps,
                "bpm": bpm_override if bpm_override is not None else active_cfg.timing.bpm,
                "events": [
                    {
                        "key": ev.key,
                        "frame_index": ev.frame_index,
                        "timestamp_sec": ev.timestamp_sec,
                        "intensity": ev.intensity,
                    }
                    for ev in all_triggers
                ],
            }
            with open(intermediate_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            logger.info("Intermediate trigger data saved to '%s'", intermediate_path)

        # --- Phase 3: quantize, assign durations, group chords ---
        timing = TimingEngine(active_cfg.timing, fps, bpm_override)
        quantized = timing.quantize(all_triggers)
        durations = timing.assign_durations(quantized)

        grouper = ChordGrouper(
            detection_cfg=active_cfg.detection,
            timing_cfg=active_cfg.timing,
            fps=fps,
            grid_duration_sec=timing.grid_duration_sec,
        )
        tokens = grouper.group(quantized, durations)

        # --- Phase 4: write output ---
        writer = TokenWriter(active_cfg.timing)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            writer.write(tokens, timing.bpm, fh)

        logger.info("Output written to '%s' (%d tokens)", output_path, len(tokens))


def main() -> None:
    """CLI entry point for the genshin-parse command."""
    parser = argparse.ArgumentParser(
        description="Vision Parser: extract sheet music tokens from Genshin instrument gameplay video."
    )
    parser.add_argument("--video", required=True, help="Path to input video file.")
    parser.add_argument(
        "--output",
        default=str(_DEFAULT_OUTPUT / "output.txt"),
        help="Path for the output .txt token file. Default: output/output.txt",
    )
    parser.add_argument(
        "--config",
        default=None,
        help=(
            "Path to ROI profile JSON. "
            "Default: auto-selected by video resolution "
            "(≤960px wide → lyre_848x480.json, else lyre_1080p.json). "
            "ROI positions in the config are always overridden by auto-detection; "
            "only the detection channel/thresholds matter."
        ),
    )
    parser.add_argument("--bpm", type=float, default=None, help="Override BPM from config.")
    parser.add_argument(
        "--intermediate",
        default=None,
        help="Optional path to save intermediate trigger JSON for debugging.",
    )
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG logging.")
    args = parser.parse_args()

    setup_logging(logging.DEBUG if args.debug else logging.INFO)

    config_path = args.config if args.config else str(_auto_config(args.video))
    cfg = InstrumentConfig.from_json(config_path)
    pipeline = ParserPipeline(cfg)
    pipeline.run(
        video_path=args.video,
        output_path=args.output,
        bpm_override=args.bpm,
        intermediate_path=args.intermediate,
    )


if __name__ == "__main__":
    main()
