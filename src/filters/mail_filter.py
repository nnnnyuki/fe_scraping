from __future__ import annotations
import sys
import email
from email.header import decode_header
from email.message import Message
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
from loguru import logger

from src.common.text_normalizer import html_to_text, normalize_text


# ===== ロガー設定（フィルタ専用ログ）=====
BASE_DIR = Path(__file__).resolve().parents[2]  # src -> fe_scraping ルート
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 重複ハンドラ防止
logger.remove()

# コンソール出力（必要な場合のみ）
logger.add(
    sys.stderr,
    level="INFO",
    # ← 中括弧は 1 個でOK
    format="[{time:YYYY-MM-DD HH:mm:ss}] {message}",
    backtrace=False,
    diagnose=False,
)

# ファイル出力（本命）
logger.add(
    LOG_DIR / "filtering.log",
    rotation="1 day",
    level="INFO",
    # ← こちらも同様
    format="[{time:YYYY-MM-DD HH:mm:ss}] {message}",
)



# ===== 設定読み込み =====
def load_filter_config(path: Optional[Path] = None) -> Dict:
    if path is None:
        path = BASE_DIR / "config" / "filtering.yml"
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ===== ユーティリティ =====
def _decode_mime_words(value: Optional[str]) -> str:
    """=?utf-8?B?...?= のようなMIMEエンコードをデコード"""
    if not value:
        return ""
    try:
        parts = decode_header(value)
        decoded = []
        for text, charset in parts:
            if isinstance(text, bytes):
                decoded.append(text.decode(charset or "utf-8", errors="ignore"))
            else:
                decoded.append(text)
        return "".join(decoded)
    except Exception:
        return value or ""


def _extract_subject_and_body(msg: Message) -> Tuple[str, str]:
    # 件名
    subject_raw = msg.get("Subject", "")
    subject = _decode_mime_words(subject_raw)

    # 本文（text/plain優先、なければtext/html）
    text_plain_parts: List[str] = []
    text_html_parts: List[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            ctype = (part.get_content_type() or "").lower()
            disp = (part.get("Content-Disposition") or "").lower()
            if ctype.startswith("text/") and "attachment" not in disp:
                try:
                    payload = part.get_payload(decode=True) or b""
                    charset = part.get_content_charset() or "utf-8"
                    text = payload.decode(charset, errors="ignore")
                except Exception:
                    continue
                if ctype == "text/plain":
                    text_plain_parts.append(text)
                elif ctype == "text/html":
                    text_html_parts.append(text)
    else:
        # 単一パート
        try:
            payload = msg.get_payload(decode=True) or b""
            charset = msg.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="ignore")
        except Exception:
            text = ""
        ctype = (msg.get_content_type() or "").lower()
        if ctype == "text/plain":
            text_plain_parts.append(text)
        elif ctype == "text/html":
            text_html_parts.append(text)

    body = ""
    if text_plain_parts:
        body = "\n".join(text_plain_parts)
    elif text_html_parts:
        body = html_to_text("\n".join(text_html_parts))

    return subject, body


IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "bmp", "webp"}
IMAGE_MIME_PREFIX = "image/"


def _detect_blocked_attachment(msg: Message, blocked_exts: set[str]) -> Optional[str]:
    """
    ブロック対象の添付が見つかればファイル名を返す。
    画像（image/*）は判定から除外。
    """
    for part in msg.walk():
        filename = part.get_filename()
        if not filename:
            continue

        # 画像は除外対象外
        ctype = (part.get_content_type() or "").lower()
        if ctype.startswith(IMAGE_MIME_PREFIX):
            continue

        fname = _decode_mime_words(filename)
        ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""

        if ext in IMAGE_EXTS:
            continue

        if ext in blocked_exts:
            return fname

        # Content-Disposition のみでのファイル名は必要に応じて拡張可
    return None


# ===== 判定結果 =====
from dataclasses import dataclass

@dataclass
class FilterResult:
    pass_through: bool  # 通過なら True
    reason: Optional[str] = None  # "attachment" | "keyword" | None
    detail: Optional[str] = None  # ファイル名 or ヒット語
    subject: str = ""


# ===== メイン判定 =====
def filter_message(msg: Message, config: Dict) -> FilterResult:
    """
    処理順序:
      1) 添付ファイルチェック（即除外）
      2) 件名・本文を正規化
      3) キーワードヒット（即除外）
      4) どちらも無ければ通過
    """
    blocked_exts = set((config.get("attachments", {}) or {}).get("blocked_extensions", []))
    keywords = (config.get("keywords", {}) or {}).get("blocklist", [])

    norm_conf = (config.get("normalization", {}) or {})
    to_half = bool(norm_conf.get("to_half_width", True))
    unify_k = bool(norm_conf.get("unify_kana", True))
    trim_sp = bool(norm_conf.get("trim_spaces", True))

    # 1) 添付ファイルブロック
    blocked_file = _detect_blocked_attachment(msg, blocked_exts)
    subject_raw, body_raw = _extract_subject_and_body(msg)
    if blocked_file:
        logger.info(f"除外: attachment (file={blocked_file})")
        return FilterResult(False, reason="attachment", detail=blocked_file, subject=subject_raw)

    # 2) 正規化
    subject_norm = normalize_text(subject_raw, to_half, unify_k, trim_sp)
    body_norm = normalize_text(body_raw, to_half, unify_k, trim_sp)

    # 3) キーワード（正規化した本文・件名に対して、正規化したキーワードで部分一致）
    keyword_norms = [normalize_text(k, to_half, unify_k, trim_sp) for k in keywords]
    haystack = f"{subject_norm} {body_norm}"

    for kw in keyword_norms:
        if kw and kw in haystack:
            logger.info(f"除外: keyword (hit={kw})")
            return FilterResult(False, reason="keyword", detail=kw, subject=subject_raw)

    # 4) 通過
    logger.info(f'通過: 案件メール (subject="{subject_raw}")')
    return FilterResult(True, reason=None, subject=subject_raw)
