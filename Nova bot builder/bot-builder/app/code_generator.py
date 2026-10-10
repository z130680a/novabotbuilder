from __future__ import annotations

import json
import sys
from pathlib import Path


def get_base_dir() -> Path:

    if getattr(sys, "frozen", False):
        return Path(
            sys.executable
        ).resolve().parent

    return Path(
        __file__
    ).resolve().parent.parent


BASE_DIR = get_base_dir()

GENERATED_DIR = (
    BASE_DIR / "generated_bots"
)

GENERATED_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT_FILE = (
    GENERATED_DIR / "generated_bot.py"
)


def generate_bot_code(
    spec: dict,
):

    bot_spec = dict(spec)

    bot_spec.setdefault(
        "active",
        True,
    )

    source = f'''\
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

BOT_SPEC = json.loads(
    r"""{json.dumps(
        bot_spec,
        ensure_ascii=False,
    )}"""
)

from app.bot_runtime import (
    ReservationEngine,
    main,
)


if __name__ == "__main__":
    main()
'''

    OUTPUT_FILE.write_text(
        source,
        encoding="utf-8",
    )

    return OUTPUT_FILE