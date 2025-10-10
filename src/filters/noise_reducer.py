# src/filters/noise_reducer.py
from __future__ import annotations
import re

_noise_rules = [
    # 署名ブロックの典型
    (r"(?is)\n--+\s*\n.*$", ""),                     # -- 署名
    (r"(?is)\n^={3,}.*$", ""),                       # === 区切り以降
    # 免責事項・機密情報
    (r"(?is)このメールは.*?機密.*?含まれている.*?$", ""),
    (r"(?is)This email.*?confidential.*?$", ""),
    # メールマガジン・配信停止
    (r"(?is)配信停止.*?こちら.*?$", ""),
    (r"(?is)unsubscribe.*?$", ""),
    # 引用履歴（From: / On ... wrote: / > など）
    (r"(?im)^\s*>.*$", ""),                          # > 引用行
    (r"(?is)\nOn .*? wrote:\s*$.*", ""),             # Gmail系
    # 過剰な空行の圧縮
    (r"\n{3,}", "\n\n"),
]

def reduce_noise(text: str) -> str:
    if not text:
        return ""
    s = text
    for pat, rep in _noise_rules:
        s = re.sub(pat, rep, s)
    return s.strip()
