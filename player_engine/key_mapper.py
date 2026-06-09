"""Maps Genshin Lyre key names to Windows DirectInput scancodes."""

from __future__ import annotations

import json
from pathlib import Path

from shared.constants import CANONICAL_KEY_SET

_DEFAULT_SCANCODES = (
    Path(__file__).parent.parent / "config" / "key_mappings" / "lyre_scancodes.json"
)


class KeyMapper:
    """Loads a key-name → scancode mapping from a JSON file.

    The JSON must contain an entry for every key in :data:`CANONICAL_KEY_SET`
    (21 keys). Scancodes are Set 1 / Make codes for a standard US keyboard.

    Args:
        cfg_path: Path to the scancodes JSON file. Defaults to
            ``config/key_mappings/lyre_scancodes.json``.

    Raises:
        FileNotFoundError: If the JSON file does not exist.
        ValueError: If any canonical key is missing from the mapping.
    """

    def __init__(self, cfg_path: str | Path | None = None) -> None:
        path = Path(cfg_path) if cfg_path else _DEFAULT_SCANCODES
        with open(path, encoding="utf-8") as fh:
            raw: dict[str, int] = json.load(fh)

        missing = CANONICAL_KEY_SET - set(raw)
        if missing:
            raise ValueError(
                f"Scancode map at {path} is missing keys: {sorted(missing)}"
            )

        self._map: dict[str, int] = {k: int(v) for k, v in raw.items()}

    def scancode(self, key: str) -> int:
        """Return the scancode for a single key name.

        Args:
            key: Key name, e.g. ``"A"``.

        Returns:
            Integer scancode.

        Raises:
            KeyError: If *key* is not in the mapping.
        """
        return self._map[key]

    def scancodes(self, keys: list[str]) -> list[int]:
        """Return scancodes for a list of key names.

        Args:
            keys: Key names to look up.

        Returns:
            List of integer scancodes in the same order as *keys*.
        """
        return [self._map[k] for k in keys]
