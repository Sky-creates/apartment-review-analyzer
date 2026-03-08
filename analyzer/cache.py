"""File-based JSON cache stored in ./cache/."""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Optional


class Cache:
    """Transparent file-based cache using sha256-keyed JSON files."""

    def __init__(self, cache_dir: str = "./cache", enabled: bool = True):
        self.cache_dir = Path(cache_dir)
        self.enabled = enabled
        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key_to_path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode()).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def get(self, key: str) -> Optional[Any]:
        if not self.enabled:
            return None
        path = self._key_to_path(key)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def set(self, key: str, value: Any) -> None:
        if not self.enabled:
            return
        path = self._key_to_path(key)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(value, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def exists(self, key: str) -> bool:
        if not self.enabled:
            return False
        return self._key_to_path(key).exists()
