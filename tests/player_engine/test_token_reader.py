"""Unit tests for player_engine.token_reader."""

from __future__ import annotations

import textwrap
import pytest
from pathlib import Path

from player_engine.token_reader import TokenReader, PlayEvent, _duration_sec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse(content: str) -> tuple[float, list[PlayEvent]]:
    """Write *content* to a temp file and parse it."""
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write(textwrap.dedent(content))
        name = fh.name
    try:
        return TokenReader().parse(name)
    finally:
        os.unlink(name)


# ---------------------------------------------------------------------------
# BPM header
# ---------------------------------------------------------------------------

def test_bpm_integer():
    bpm, events = _parse("BPM 120\nA\n")
    assert bpm == 120.0


def test_bpm_float():
    bpm, _ = _parse("BPM 100.5\nA\n")
    assert bpm == pytest.approx(100.5)


def test_missing_bpm_raises():
    with pytest.raises(ValueError, match="BPM"):
        _parse("A/4 B/4\n")


# ---------------------------------------------------------------------------
# Single note
# ---------------------------------------------------------------------------

def test_note_no_denom():
    """Bare key name → denom=1 (whole note, 4 beats)."""
    _, events = _parse("BPM 120\nA\n")
    assert len(events) == 1
    e = events[0]
    assert e.keys == ["A"]
    assert e.duration_denom == 1
    assert e.duration_sec == pytest.approx(2.0)   # (60/120)*(4/1) = 2s
    assert not e.is_rest


def test_note_quarter():
    _, events = _parse("BPM 120\nA/4\n")
    e = events[0]
    assert e.keys == ["A"]
    assert e.duration_denom == 4
    assert e.duration_sec == pytest.approx(0.5)   # (60/120)*(4/4) = 0.5s


def test_note_eighth():
    _, events = _parse("BPM 120\nD/8\n")
    assert events[0].duration_sec == pytest.approx(0.25)


def test_note_half():
    _, events = _parse("BPM 120\nQ/2\n")
    assert events[0].duration_sec == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Chord
# ---------------------------------------------------------------------------

def test_chord_no_denom():
    _, events = _parse("BPM 120\n[ADS]\n")
    e = events[0]
    assert e.keys == ["A", "D", "S"]
    assert e.duration_denom == 1
    assert not e.is_rest


def test_chord_with_denom():
    _, events = _parse("BPM 120\n[ADS]/2\n")
    e = events[0]
    assert e.duration_sec == pytest.approx(1.0)
    assert e.duration_denom == 2


def test_chord_keys_sorted():
    """Keys should come out alpha-sorted regardless of input order."""
    _, events = _parse("BPM 120\n[DSA]/4\n")
    assert events[0].keys == ["A", "D", "S"]


# ---------------------------------------------------------------------------
# Rest
# ---------------------------------------------------------------------------

def test_rest_no_denom():
    _, events = _parse("BPM 120\n-\n")
    e = events[0]
    assert e.is_rest
    assert e.keys == []
    assert e.duration_denom == 1


def test_rest_eighth():
    _, events = _parse("BPM 120\n-/8\n")
    e = events[0]
    assert e.is_rest
    assert e.duration_sec == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# Multi-line file
# ---------------------------------------------------------------------------

def test_multiline_full_sequence():
    content = """\
        BPM 120
        D H J Q/2 -/8
        [ADS]/2 -
    """
    bpm, events = _parse(content)
    assert bpm == 120.0
    assert len(events) == 7

    keys_sequence = [e.keys for e in events]
    assert keys_sequence[0] == ["D"]
    assert keys_sequence[1] == ["H"]
    assert keys_sequence[2] == ["J"]
    assert keys_sequence[3] == ["Q"]
    assert events[3].duration_denom == 2
    assert events[4].is_rest
    assert events[4].duration_denom == 8
    assert keys_sequence[5] == ["A", "D", "S"]
    assert events[6].is_rest


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

def test_unknown_key_in_note_raises():
    # "P" is a valid uppercase letter but not in CANONICAL_KEY_SET
    with pytest.raises(ValueError, match="Unknown key"):
        _parse("BPM 120\nP\n")


def test_unknown_key_in_chord_raises():
    # "P" passes the [A-Z]+ regex but is not in CANONICAL_KEY_SET
    with pytest.raises(ValueError, match="Unknown key"):
        _parse("BPM 120\n[APD]\n")


def test_unparseable_token_raises():
    with pytest.raises(ValueError, match="Cannot parse token"):
        _parse("BPM 120\n???\n")


# ---------------------------------------------------------------------------
# Duration math
# ---------------------------------------------------------------------------

def test_duration_sec_whole():
    assert _duration_sec(120.0, 1) == pytest.approx(2.0)


def test_duration_sec_quarter():
    assert _duration_sec(120.0, 4) == pytest.approx(0.5)


def test_duration_sec_eighth_bpm100():
    # (60/100)*(4/8) = 0.6*0.5 = 0.3s
    assert _duration_sec(100.0, 8) == pytest.approx(0.3)
