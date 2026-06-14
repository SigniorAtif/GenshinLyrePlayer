"""Stub for future GUI-driven ROI calibration tool.

Planned behavior (post-MVP):
    - Accept a video path and open a reference frame
    - Overlay current ROI boxes from a config file
    - Allow drag-to-resize each box via mouse interaction
    - Write the updated coordinates back to the JSON config on save

Implementation notes (for when this gets built):
    - Dear PyGui is preferred over tkinter for styling and widget richness
    - OpenCV highgui (cv2.setMouseCallback) is an acceptable zero-dep fallback
    - The tool should call ROIManager.debug_overlay_cropped() for initial rendering
    - Resolution auto-scaling must be disabled during calibration (user works
      at the actual video resolution and saves those raw coordinates)
"""


class Calibrator:
    """GUI calibration tool for ROI bounding boxes.

    Not implemented in Part 1. Raises NotImplementedError on construction.
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "Calibrator is a future milestone stub. "
            "Use tools/roi_debugger.py for manual overlay inspection."
        )
