"""Unit tests for player_engine.timing_scheduler."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, call, patch

import pytest

from player_engine.input_injector import DryRunInjector
from player_engine.key_mapper import KeyMapper
from player_engine.timing_scheduler import TimingScheduler, _wait_until
from player_engine.token_reader import PlayEvent, _duration_sec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mapper() -> KeyMapper:
    """Return a real KeyMapper using the default scancodes config."""
    return KeyMapper()


def _note(key: str, denom: int, bpm: float = 120.0) -> PlayEvent:
    return PlayEvent(
        keys=[key],
        duration_sec=_duration_sec(bpm, denom),
        duration_denom=denom,
        is_rest=False,
    )


def _rest(denom: int, bpm: float = 120.0) -> PlayEvent:
    return PlayEvent(
        keys=[],
        duration_sec=_duration_sec(bpm, denom),
        duration_denom=denom,
        is_rest=True,
    )


# ---------------------------------------------------------------------------
# Duration math sanity checks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("denom,expected_sec", [
    (1, 2.0),    # whole note at BPM 120
    (2, 1.0),    # half
    (4, 0.5),    # quarter
    (8, 0.25),   # eighth
])
def test_duration_values(denom, expected_sec):
    ev = _note("A", denom, bpm=120.0)
    assert ev.duration_sec == pytest.approx(expected_sec)


def test_speed_factor_doubles_duration():
    """speed_factor=0.5 means 2× slower → gap between events is 2× as long.

    Uses two events so the scheduler must wait the full adjusted duration
    before firing the second event.
    """
    mapper = _make_mapper()
    injector = DryRunInjector()
    scheduler = TimingScheduler(key_mapper=mapper, speed_factor=0.5)

    # Two quarter notes; at 0.5× speed each takes 1.0s → total gap ~1.0s
    events = [_note("A", 4), _note("D", 4)]

    start = time.perf_counter()
    scheduler.run(events, injector, countdown_sec=0.0)
    elapsed = time.perf_counter() - start

    # First event fires immediately; second fires after 1.0s (0.5s / 0.5)
    assert elapsed == pytest.approx(1.0, abs=0.2)


def test_speed_factor_halves_duration():
    """speed_factor=2.0 means 2× faster → gap between events is halved.

    Uses two events so the scheduler must wait the adjusted duration.
    """
    mapper = _make_mapper()
    injector = DryRunInjector()
    scheduler = TimingScheduler(key_mapper=mapper, speed_factor=2.0)

    # Two quarter notes; at 2× speed each takes 0.25s → gap ~0.25s
    events = [_note("A", 4), _note("D", 4)]

    start = time.perf_counter()
    scheduler.run(events, injector, countdown_sec=0.0)
    elapsed = time.perf_counter() - start

    assert elapsed == pytest.approx(0.25, abs=0.1)


# ---------------------------------------------------------------------------
# Dry-run: no SendInput calls, tap called on DryRunInjector
# ---------------------------------------------------------------------------

def test_dry_run_calls_tap():
    """DryRunInjector.tap should be called for note events."""
    mapper = _make_mapper()
    injector = MagicMock(spec=DryRunInjector)
    scheduler = TimingScheduler(key_mapper=mapper)

    events = [_note("A", 4), _rest(4), _note("D", 4)]
    scheduler.run(events, injector, countdown_sec=0.0)

    # tap called for notes only (not rests)
    assert injector.tap.call_count == 2


def test_dry_run_no_tap_for_rest():
    """Rests must not trigger tap."""
    mapper = _make_mapper()
    injector = MagicMock(spec=DryRunInjector)
    scheduler = TimingScheduler(key_mapper=mapper)

    scheduler.run([_rest(4)], injector, countdown_sec=0.0)
    injector.tap.assert_not_called()


# ---------------------------------------------------------------------------
# Scancode passing
# ---------------------------------------------------------------------------

def test_correct_scancodes_passed_to_injector():
    """Scheduler must look up scancodes and pass them to tap."""
    mapper = _make_mapper()
    injector = MagicMock(spec=DryRunInjector)
    scheduler = TimingScheduler(key_mapper=mapper)

    scheduler.run([_note("A", 4)], injector, countdown_sec=0.0)

    expected_sc = mapper.scancodes(["A"])
    injector.tap.assert_called_once_with(expected_sc)


def test_chord_scancodes():
    """Chord events pass all key scancodes at once."""
    mapper = _make_mapper()
    injector = MagicMock(spec=DryRunInjector)
    scheduler = TimingScheduler(key_mapper=mapper)

    chord_event = PlayEvent(
        keys=["A", "D", "S"],
        duration_sec=0.5,
        duration_denom=4,
        is_rest=False,
    )
    scheduler.run([chord_event], injector, countdown_sec=0.0)
    injector.tap.assert_called_once_with(mapper.scancodes(["A", "D", "S"]))


# ---------------------------------------------------------------------------
# _wait_until helper
# ---------------------------------------------------------------------------

def test_wait_until_accuracy():
    """_wait_until should return within 5ms of the target."""
    target = time.perf_counter() + 0.05  # 50ms ahead
    _wait_until(target)
    delta = time.perf_counter() - target
    assert 0 <= delta < 0.005  # fired within 5ms after target
