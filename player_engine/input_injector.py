"""Windows SendInput wrapper for DirectInput-compatible scancode injection."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging

logger = logging.getLogger(__name__)

# Windows INPUT type constant
_INPUT_KEYBOARD = 1

# dwFlags values
_KEYEVENTF_SCANCODE = 0x0008
_KEYEVENTF_KEYUP = 0x0002


class _KEYBDINPUT(ctypes.Structure):
    """Inner struct for keyboard input within the INPUT union."""

    _fields_ = [
        ("wVk", ctypes.wintypes.WORD),
        ("wScan", ctypes.wintypes.WORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT_UNION(ctypes.Union):
    """Union that holds the keyboard input structure."""

    _fields_ = [("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
    """Windows INPUT structure passed to SendInput."""

    _fields_ = [
        ("type", ctypes.wintypes.DWORD),
        ("union", _INPUT_UNION),
    ]


def _make_key_input(scancode: int, key_up: bool) -> _INPUT:
    """Build a single keyboard INPUT record.

    Args:
        scancode: Hardware scancode (Set 1 Make code).
        key_up: True for a key-release event, False for key-press.

    Returns:
        Populated :class:`_INPUT` structure.
    """
    flags = _KEYEVENTF_SCANCODE
    if key_up:
        flags |= _KEYEVENTF_KEYUP
    inp = _INPUT(type=_INPUT_KEYBOARD)
    inp.union.ki = _KEYBDINPUT(wVk=0, wScan=scancode, dwFlags=flags, time=0)
    return inp


class InputInjector:
    """Sends hardware-level keyboard events via Windows ``SendInput``.

    Uses ``KEYEVENTF_SCANCODE`` so events bypass the virtual-key layer and
    reach DirectInput-aware applications (e.g. Genshin Impact).

    Tap semantics: :meth:`tap` fires all key-down events then all key-up events
    in a **single** ``SendInput`` call — the OS treats them as simultaneous,
    which is essential for chord accuracy.
    """

    def tap(self, scancodes: list[int]) -> None:
        """Press and immediately release one or more keys.

        All keys are pressed simultaneously (single ``SendInput`` call with
        N keydowns followed by N keyups), then released simultaneously.

        Args:
            scancodes: Hardware scancodes to inject. For a single note, pass a
                one-element list. For a chord, pass all keys at once.
        """
        if not scancodes:
            return

        n = len(scancodes)
        inputs = (_INPUT * (2 * n))()

        for i, sc in enumerate(scancodes):
            inputs[i] = _make_key_input(sc, key_up=False)
        for i, sc in enumerate(scancodes):
            inputs[n + i] = _make_key_input(sc, key_up=True)

        sent = ctypes.windll.user32.SendInput(
            2 * n, ctypes.cast(inputs, ctypes.POINTER(_INPUT)), ctypes.sizeof(_INPUT)
        )
        if sent != 2 * n:
            logger.warning(
                "SendInput sent %d of %d events (scancodes=%s)",
                sent, 2 * n, scancodes,
            )
        else:
            logger.debug("tap scancodes=%s", scancodes)


class DryRunInjector:
    """Drop-in replacement for :class:`InputInjector` that logs instead of injecting.

    Safe to use outside the game for testing timing and token parsing without
    any risk of accidental key presses in other applications.
    """

    def tap(self, scancodes: list[int]) -> None:
        """Log the tap without calling ``SendInput``.

        Args:
            scancodes: Scancodes that *would* be injected.
        """
        logger.info("DRY-RUN tap scancodes=%s", scancodes)
