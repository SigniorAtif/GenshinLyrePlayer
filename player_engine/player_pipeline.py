"""Top-level orchestrator for the Player Engine pipeline."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from player_engine.input_injector import DryRunInjector, InputInjector
from player_engine.key_mapper import KeyMapper
from player_engine.timing_scheduler import TimingScheduler
from player_engine.token_reader import TokenReader
from shared.logging_config import setup_logging

logger = logging.getLogger(__name__)

_DEFAULT_SCANCODES = (
    Path(__file__).parent.parent / "config" / "key_mappings" / "lyre_scancodes.json"
)


class PlayerPipeline:
    """Full Player Engine pipeline: ``.txt`` token file → DirectInput keystrokes.

    Wires :class:`~player_engine.token_reader.TokenReader` →
    :class:`~player_engine.key_mapper.KeyMapper` →
    :class:`~player_engine.input_injector.InputInjector` →
    :class:`~player_engine.timing_scheduler.TimingScheduler`.

    Args:
        scancodes_path: Path to the key-name → scancode JSON config. Defaults
            to ``config/key_mappings/lyre_scancodes.json``.
        speed_factor: Playback speed multiplier (1.0 = normal).
    """

    def __init__(
        self,
        scancodes_path: str | Path | None = None,
        speed_factor: float = 1.0,
    ) -> None:
        self._scancodes_path = scancodes_path or _DEFAULT_SCANCODES
        self._speed_factor = speed_factor

    def run(
        self,
        token_path: str | Path,
        *,
        dry_run: bool = False,
        countdown_sec: float = 3.0,
    ) -> None:
        """Parse a token file and play it back.

        Args:
            token_path: Path to the ``.txt`` token file produced by
                ``genshin-parse``.
            dry_run: If ``True``, uses :class:`~player_engine.input_injector.DryRunInjector`
                — logs all events but never calls ``SendInput``. Safe to run
                without the game open.
            countdown_sec: Seconds to wait before the first note fires (gives
                time to focus the game window). Ignored in dry-run mode
                (set to 0 automatically).
        """
        reader = TokenReader()
        bpm, events = reader.parse(token_path)
        logger.info(
            "Parsed %d events at BPM %.1f from '%s'",
            len(events),
            bpm,
            token_path,
        )

        mapper = KeyMapper(self._scancodes_path)
        injector: InputInjector | DryRunInjector
        if dry_run:
            injector = DryRunInjector()
            countdown_sec = 0.0  # no need to wait in dry-run
            logger.info("DRY-RUN mode — SendInput calls suppressed")
        else:
            injector = InputInjector()

        scheduler = TimingScheduler(key_mapper=mapper, speed_factor=self._speed_factor)
        scheduler.run(events, injector, countdown_sec=countdown_sec)


def main() -> None:
    """CLI entry point for the ``genshin-play`` command."""
    parser = argparse.ArgumentParser(
        description=(
            "Player Engine: replay a Genshin sheet music token file "
            "by injecting DirectInput keystrokes."
        )
    )
    parser.add_argument(
        "--token",
        required=True,
        help="Path to the .txt token file produced by genshin-parse.",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Playback speed multiplier. 1.0 = normal, 0.8 = 80%% speed. Default: 1.0",
    )
    parser.add_argument(
        "--countdown",
        type=float,
        default=3.0,
        help=(
            "Seconds to wait before the first note fires. "
            "Use this time to focus the game window. Default: 3.0"
        ),
    )
    parser.add_argument(
        "--scancodes",
        default=None,
        help="Path to a custom key→scancode JSON. Default: config/key_mappings/lyre_scancodes.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Log all events without sending any keystrokes. "
            "Safe to run outside the game."
        ),
    )
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG logging.")
    args = parser.parse_args()

    setup_logging(logging.DEBUG if args.debug else logging.INFO)

    pipeline = PlayerPipeline(
        scancodes_path=args.scancodes,
        speed_factor=args.speed,
    )
    pipeline.run(
        token_path=args.token,
        dry_run=args.dry_run,
        countdown_sec=args.countdown,
    )


if __name__ == "__main__":
    main()
