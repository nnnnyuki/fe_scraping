from __future__ import annotations
import re
import unicodedata
from typing import Optional

try:
    import jaconv  # あると精度UP（なくても動く）
except Exception:
    jaconv = None

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None


def html_to_text(html: str) -> str:
    """HTML文字列から可読テキストを抽出"""
    if not html:
        return ""
    if BeautifulSoup:
        soup = BeautifulSoup(html, "html.parser")
        # script/style除去
        for tag in soup(["script", "style"]):
            tag.extract()
        text = soup.get_text(separator=" ")
    else:
        # フォールバック（簡易除去）
        text = re.sub(r"<[^>]+>", " ", html)
    return text


def normalize_text(
    text: Optional[str],
    to_half_width: bool = True,
    unify_kana: bool = True,
    trim_spaces: bool = True,
) -> str:
    """
    日本語メールのための正規化：
      - 全角→半角（NFKC）
      - ひらがな/カタカナ統一
      - 余分な空白の圧縮
      - ASCIIは小文字化
    """
    if not text:
        return ""

    s = text

    # 全角→半角。句読点や記号も揃う（数字・英字・記号の揺れ対策）
    if to_half_width:
        s = unicodedata.normalize("NFKC", s)

    # ひらがな/カタカナ統一（今回はカタカナへ統一）
    if unify_kana:
        if jaconv:
            s = jaconv.hira2kata(s)
        else:
            # jaconv不在時の簡易対応（ひらがな→カタカナ）
            s = "".join(
                chr(ord(ch) + 0x60) if "ぁ" <= ch <= "ゖ" else ch for ch in s
            )

    # ASCIIは小文字化（英語混在の揺れ対策）
    s = s.lower()

    # 余分な空白を1個に圧縮
    if trim_spaces:
        s = re.sub(r"\s+", " ", s).strip()

    return s
