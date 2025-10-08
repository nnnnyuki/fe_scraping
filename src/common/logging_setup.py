# src/common/logging_setup.py
from __future__ import annotations

from pathlib import Path
from loguru import logger
from datetime import datetime
from zoneinfo import ZoneInfo  # Python 3.9+

import sys

# JST のタイムスタンプを extra に差し込むパッチ
def _inject_jst(record):
    record["extra"]["jst"] = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S")

# 共通フォーマット：extra[jst] を使う
FORMAT = "<green>{extra[jst]}</green> | <level>{level}</level> | {message}"

def setup_logger(log_file: Path):
    logger.remove()

    # 各ログレコードに JST を注入
    patched = logger.patch(_inject_jst)

    # コンソール
    patched.add(
        sys.stderr,
        level="INFO",
        format=FORMAT,
    )

    # ファイル
    patched.add(
        log_file,
        level="INFO",
        rotation="00:00",
        retention="30 days",
        encoding="utf-8",
        format=FORMAT,
    )

    return patched
