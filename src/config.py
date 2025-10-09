
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
IMAP_HOST: str = _env("IMAP_HOST").strip().rstrip("/")
IMAP_PORT: int = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER: str = _env("IMAP_USER").strip()
IMAP_PASS: str = _env("IMAP_PASS").strip()
IMAP_MAILBOX: str = os.getenv("IMAP_MAILBOX", "INBOX").strip()

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
    """
    実行前の恒久チェック（ジョブ冒頭で呼ぶ想定）。
    - 必須値の空チェック
    - ディレクトリ存在確認
    - 正規化の取りこぼし検知（末尾'/' や空白）
    - ポート範囲検証
    - （任意）DNS 解決チェック
    """
    # 必須項目
    if not IMAP_HOST or not IMAP_USER:
        raise RuntimeError("IMAP_HOST / IMAP_USER が空です")
    if not IMAP_MAILBOX:
        raise RuntimeError("IMAP_MAILBOX が空です")

    # ディレクトリ存在
    if not MAIL_ARCHIVE_DIR.exists():
        raise RuntimeError(f"{MAIL_ARCHIVE_DIR} がありません")
    if not LOG_DIR.exists():
        raise RuntimeError(f"{LOG_DIR} がありません")

    # 正規化の取りこぼし検知（保険）
    if IMAP_HOST.endswith("/"):
        raise RuntimeError("IMAP_HOST の末尾に '/' が残っています")
    if " " in IMAP_HOST:
        raise RuntimeError("IMAP_HOST に空白が含まれています")

    # ポート範囲
    if not (1 <= IMAP_PORT <= 65535):
        raise RuntimeError("IMAP_PORT が 1..65535 の範囲外です")

    # オプション: DNS 解決まで確認（STRICT_CONFIG_DNS=1 で有効化）
    import os as _os
    if _os.getenv("STRICT_CONFIG_DNS") == "1":
        import socket as _socket
        try:
            _socket.getaddrinfo(IMAP_HOST, IMAP_PORT)
        except _socket.gaierror as e:
            raise RuntimeError(f"IMAP_HOST の名前解決に失敗: {IMAP_HOST}:{IMAP_PORT} ({e})")
