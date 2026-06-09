"""Parses the .txt sheet music token format produced by vision_parser."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from shared.constants import CANONICAL_KEY_SET


# Regex patterns for the three token types.
_RE_NOTE = re.compile(r"^([A-Z])(?:/(\d+))?$")
_RE_CHORD = re.compile(r"^\[([A-Z]+)\](?:/(\d+))?$")
_RE_REST = re.compile(r"^-(?:/(\d+))?$")
_RE_BPM = re.compile(r"^BPM\s+(\d+(?:\.\d+)?)$")


@dataclass(frozen=True)
class PlayEvent:
    """A single playback event derived from one token.

    Args:
        keys: Key names to press simultaneously. Empty list for a rest.
        duration_sec: Wall-clock duration of this event in seconds at the
            target BPM. Derived from ``duration_denom`` as::

                duration_sec = (60.0 / bpm) * (4.0 / duration_denom)

            denom=1 → whole (4 beats), denom=2 → half, denom=4 → quarter,
            denom=8 → eighth.
        duration_denom: Original note-value denominator from the token file.
        is_rest: True when this event carries no key presses (silence gap).
    """

    keys: list[str]
    duration_sec: float
    duration_denom: int
    is_rest: bool


class TokenReader:
    """Parses a token ``.txt`` file into a list of :class:`PlayEvent` objects.

    The file format is::

        BPM 120
        D H J Q/2 -/8 J H F
        [ADS]/2 - Q/8

    Rules:
    - Line 1 must be ``BPM <value>``.
    - Remaining lines are whitespace-separated tokens.
    - Single key: ``A`` (denom=1) or ``A/4`` (quarter).
    - Chord: ``[ADS]`` or ``[ADS]/2``.
    - Rest: ``-`` or ``-/8``.
    - Duration math: ``duration_sec = (60.0 / bpm) * (4.0 / denom)``.
    """

    def parse(self, path: str | Path) -> tuple[float, list[PlayEvent]]:
        """Parse a token file.

        Args:
            path: Path to the ``.txt`` token file.

        Returns:
            Tuple of ``(bpm, events)`` where *bpm* is the effective tempo and
            *events* is the ordered list of :class:`PlayEvent` objects.

        Raises:
            ValueError: If the first line is not a valid ``BPM`` header, or if
                a token cannot be parsed.
        """
        text = Path(path).read_text(encoding="utf-8")
        lines = [ln for ln in text.splitlines() if ln.strip()]

        if not lines:
            raise ValueError(f"Token file is empty: {path}")

        bpm_match = _RE_BPM.match(lines[0].strip())
        if not bpm_match:
            raise ValueError(
                f"First line must be 'BPM <value>', got: {lines[0]!r}"
            )
        bpm = float(bpm_match.group(1))

        events: list[PlayEvent] = []
        for line in lines[1:]:
            for raw_tok in line.split():
                event = self._parse_token(raw_tok, bpm)
                events.append(event)

        return bpm, events

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_token(tok: str, bpm: float) -> PlayEvent:
        """Convert a single token string to a :class:`PlayEvent`.

        Args:
            tok: Raw token string, e.g. ``"A/4"``, ``"[ADS]/2"``, ``"-/8"``.
            bpm: Beats per minute used to compute ``duration_sec``.

        Returns:
            Corresponding :class:`PlayEvent`.

        Raises:
            ValueError: If the token cannot be matched or a key is unknown.
        """
        # Rest
        m = _RE_REST.match(tok)
        if m:
            denom = int(m.group(1)) if m.group(1) else 1
            return PlayEvent(
                keys=[],
                duration_sec=_duration_sec(bpm, denom),
                duration_denom=denom,
                is_rest=True,
            )

        # Chord
        m = _RE_CHORD.match(tok)
        if m:
            keys = list(m.group(1))  # each char is a key
            _validate_keys(keys, tok)
            denom = int(m.group(2)) if m.group(2) else 1
            return PlayEvent(
                keys=sorted(keys),
                duration_sec=_duration_sec(bpm, denom),
                duration_denom=denom,
                is_rest=False,
            )

        # Single note
        m = _RE_NOTE.match(tok)
        if m:
            key = m.group(1)
            _validate_keys([key], tok)
            denom = int(m.group(2)) if m.group(2) else 1
            return PlayEvent(
                keys=[key],
                duration_sec=_duration_sec(bpm, denom),
                duration_denom=denom,
                is_rest=False,
            )

        raise ValueError(f"Cannot parse token: {tok!r}")


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _duration_sec(bpm: float, denom: int) -> float:
    """Convert a note-value denominator to wall-clock seconds.

    Args:
        bpm: Beats per minute.
        denom: Note-value denominator (1=whole, 2=half, 4=quarter, 8=eighth).

    Returns:
        Duration in seconds.
    """
    return (60.0 / bpm) * (4.0 / denom)


def _validate_keys(keys: list[str], raw_tok: str) -> None:
    """Raise ValueError if any key is not in CANONICAL_KEY_SET.

    Args:
        keys: Key names to check.
        raw_tok: Original token string (for error messages).
    """
    for k in keys:
        if k not in CANONICAL_KEY_SET:
            raise ValueError(
                f"Unknown key {k!r} in token {raw_tok!r}. "
                f"Expected one of {sorted(CANONICAL_KEY_SET)}"
            )
