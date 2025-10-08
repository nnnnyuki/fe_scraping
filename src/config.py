
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# 1) .env を読み込む（プロジェクト直下を優先）
load_dotenv()

def _env(key: str, default: Optional[str] = None) -> str:
    """必須の環境変数を取得。未設定なら即エラーで止める。"""
    v = os.getenv(key, default)
    if v is None or str(v).strip() == "":
        raise RuntimeError(f"Missing env: {key}")
    return v

# 2) IMAP 接続設定
IMAP_HOST: str = _env("IMAP_HOST")
IMAP_PORT: int = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER: str = _env("IMAP_USER")
IMAP_PASS: str = _env("IMAP_PASS")
IMAP_MAILBOX: str = os.getenv("IMAP_MAILBOX", "INBOX")

# 3) パス設定（データ格納場所）
DATA_ROOT: Path = Path(os.getenv("DATA_ROOT", "./data")).resolve()
MAIL_ARCHIVE_DIR: Path = DATA_ROOT / "mail_archive" / "imap"
LOG_DIR: Path = DATA_ROOT / "mail_archive" / "logs"

# 4) 保存先ディレクトリの自動作成（初回でも落ちないように）
for d in (DATA_ROOT, MAIL_ARCHIVE_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)

# 5) 便利ヘルパ
def path_for_mail_text(file_stem: str) -> Path:
    """
    例: path_for_mail_text("20251008_123456_UID9999") -> data/mail_archive/imap/20251008_123456_UID9999.txt
    """
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in file_stem)
    return MAIL_ARCHIVE_DIR / f"{safe}.txt"

def require_ready() -> None:
    """最低限の前提が満たされているか簡易チェック（ジョブの冒頭で呼ぶ想定）。"""
    assert IMAP_HOST and IMAP_USER, "IMAP_HOST / IMAP_USER が空です"
    assert MAIL_ARCHIVE_DIR.exists(), f"{MAIL_ARCHIVE_DIR} がありません"
    assert LOG_DIR.exists(), f"{LOG_DIR} がありません"
