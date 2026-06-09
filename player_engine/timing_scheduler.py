"""Absolute-deadline scheduler for token playback with sub-millisecond precision."""

from __future__ import annotations

import logging
import time

from player_engine.input_injector import DryRunInjector, InputInjector
from player_engine.key_mapper import KeyMapper
from player_engine.token_reader import PlayEvent

logger = logging.getLogger(__name__)

# Busy-wait kicks in this many seconds before the deadline.
# 2ms covers OS scheduler jitter (typical Windows timer resolution ~15ms, but
# perf_counter spin-wait is not limited by that).
_BUSYWAIT_LEAD_SEC = 0.002


def _wait_until(target: float) -> None:
    """Block until ``time.perf_counter() >= target``.

    Uses ``time.sleep`` for the bulk of the wait then spins for the final
    :data:`_BUSYWAIT_LEAD_SEC` to achieve sub-millisecond accuracy.

    Args:
        target: Absolute ``perf_counter`` timestamp to wait for.
    """
    slack = target - time.perf_counter() - _BUSYWAIT_LEAD_SEC
    if slack > 0:
        time.sleep(slack)
    while time.perf_counter() < target:
        pass  # busy-wait for final ~2ms


class TimingScheduler:
    """Replays a sequence of :class:`~player_engine.token_reader.PlayEvent` objects
    at accurate wall-clock intervals.

    Timing is based on absolute deadlines (not cumulative sleep) so quantization
    error never drifts across the song.

    Args:
        key_mapper: :class:`~player_engine.key_mapper.KeyMapper` instance used
            to convert key names to scancodes.
        speed_factor: Playback speed multiplier. ``1.0`` = normal speed,
            ``0.8`` = 80% speed (slower), ``1.25`` = faster. All durations are
            divided by this factor.
    """

    def __init__(self, key_mapper: KeyMapper, speed_factor: float = 1.0) -> None:
        self._mapper = key_mapper
        self._speed = speed_factor

    def run(
        self,
        events: list[PlayEvent],
        injector: InputInjector | DryRunInjector,
        *,
        countdown_sec: float = 3.0,
    ) -> None:
        """Play back all events in order.

        Args:
            events: Ordered list of :class:`PlayEvent` objects from
                :class:`~player_engine.token_reader.TokenReader`.
            injector: :class:`InputInjector` or :class:`DryRunInjector`.
            countdown_sec: Seconds to wait before the first note fires.
                Gives the player time to focus the game window after running
                the command. Set to 0 to start immediately.
        """
        if not events:
            logger.warning("TimingScheduler.run() called with empty event list")
            return

        logger.info(
            "Playback starting in %.1fs — switch to the game window!",
            countdown_sec,
        )
        deadline = time.perf_counter() + countdown_sec

        total = len(events)
        for idx, ev in enumerate(events):
            adjusted_duration = ev.duration_sec / self._speed

            _wait_until(deadline)

            if not ev.is_rest:
                scancodes = self._mapper.scancodes(ev.keys)
                injector.tap(scancodes)
                logger.debug(
                    "t=%.4f  keys=%s  denom=%d  dur=%.4fs",
                    time.perf_counter(),
                    ev.keys,
                    ev.duration_denom,
                    adjusted_duration,
                )

            deadline += adjusted_duration

            # Log progress every 50 events
            if (idx + 1) % 50 == 0 or (idx + 1) == total:
                logger.info("Progress: %d / %d events", idx + 1, total)

        logger.info("Playback complete.")
