# src/review/exporters.py
from __future__ import annotations
import csv
from pathlib import Path
import datetime as dt
import email
from typing import Optional

BASE_DIR = Path(__file__).resolve().parents[2]
REVIEW_DIR = BASE_DIR / "data" / "review"
REVIEW_DIR.mkdir(parents=True, exist_ok=True)

def _decode_header(value: Optional[str]) -> str:
    import email.header
    if not value:
        return ""
    parts = email.header.decode_header(value)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            try:
                out.append(text.decode(enc or "utf-8", errors="replace"))
            except LookupError:
                out.append(text.decode("utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out).strip()

def _message_datetime(msg: email.message.Message) -> dt.datetime:
    raw = msg.get("Date")
    try:
        d = email.utils.parsedate_to_datetime(raw) if raw else None
    except Exception:
        d = None
    if d is None:
        d = dt.datetime.now()
    if getattr(d, "tzinfo", None):
        d = d.astimezone(dt.timezone(dt.timedelta(hours=9))).replace(tzinfo=None)
    return d

def append_excluded(uid: bytes, msg: email.message.Message, reason: str, detail: str | None):
    d = _message_datetime(msg)
    ymd = d.strftime("%Y%m%d")
    csv_path = REVIEW_DIR / f"excluded_{ymd}.csv"
    is_new = not csv_path.exists()

    row = {
        "logged_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "uid": uid.decode(),
        "date": d.strftime("%Y-%m-%d %H:%M:%S"),
        "from": _decode_header(msg.get("From")),
        "subject": _decode_header(msg.get("Subject")),
        "reason": reason,
        "detail": detail or "",
    }

    with csv_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if is_new:
            writer.writeheader()
        writer.writerow(row)
