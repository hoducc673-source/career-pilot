from __future__ import annotations

import os
import re
from pathlib import Path


ENV_KEY_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def load_env_file(path: Path = Path(".env")) -> None:
    """Load a small KEY=VALUE env file without logging secret values."""
    if not path.exists():
        return
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f".env 第 {line_number} 行缺少等号")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not ENV_KEY_PATTERN.fullmatch(key):
            raise ValueError(f".env 第 {line_number} 行变量名不合法")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)
