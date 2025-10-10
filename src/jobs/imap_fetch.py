# -*- coding: utf-8 -*-
"""
IMAPメールを取得し、data/mail_archive/imap/ に .txt でアーカイブ保存するジョブ。
- 既定は UNSEEN（未読）のみ
- --all で ALL（既読/未読すべて）
- --since YYYY-MM-DD や --days N で期間指定
- --limit N で件数制限（新しいものから）
- --dry-run で保存せず対象だけ確認
"""

from __future__ import annotations

import argparse
import datetime as dt
import email
import email.policy
import email.header
import imaplib
import re
from typing import Iterable, Optional

from src.config import (
    IMAP_HOST, IMAP_PORT, IMAP_USER, IMAP_PASS, IMAP_MAILBOX,
    path_for_mail_text, require_ready
)

# === ここから追記: フィルタリング ===
# フィルタ設定を読み込み、各メッセージに対して通過/除外を判定します
from src.filters.mail_filter import load_filter_config, filter_message
FILTER_CONF = load_filter_config()
# === 追記ここまで ===


def _decode_header(value: Optional[str]) -> str:
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
    # タイムゾーンが付いていればJSTに寄せてnaiveに統一（ファイル名の安定化）
    if getattr(d, "tzinfo", None):
        d = d.astimezone(dt.timezone(dt.timedelta(hours=9))).replace(tzinfo=None)
    return d


def _iter_text_parts(msg: email.message.Message) -> Iterable[str]:
    """text/plain を優先。無ければ text/html を超簡易テキスト化して返す。"""
    plain = []
    html = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = (part.get_content_disposition() or "").lower()
            if disp == "attachment":
                continue
            if ctype == "text/plain":
                try:
                    plain.append(part.get_content().strip())
                except Exception:
                    payload = part.get_payload(decode=True) or b""
                    plain.append(payload.decode(part.get_content_charset() or "utf-8", "replace").strip())
            elif ctype == "text/html":
                try:
                    html.append(part.get_content())
                except Exception:
                    payload = part.get_payload(decode=True) or b""
                    html.append(payload.decode(part.get_content_charset() or "utf-8", "replace"))
    else:
        ctype = msg.get_content_type()
        if ctype == "text/plain":
            try:
                plain.append(msg.get_content().strip())
            except Exception:
                payload = msg.get_payload(decode=True) or b""
                plain.append(payload.decode(msg.get_content_charset() or "utf-8", "replace").strip())
        elif ctype == "text/html":
            try:
                html.append(msg.get_content())
            except Exception:
                payload = msg.get_payload(decode=True) or b""
                html.append(payload.decode(msg.get_content_charset() or "utf-8", "replace"))

    if plain:
        return [p for p in plain if p]

    # HTML -> 簡易テキスト化
    def _html_to_text(s: str) -> str:
        s = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", s)
        s = re.sub(r"(?is)<br\s*/?>", "\n", s)
        s = re.sub(r"(?is)</p\s*>", "\n\n", s)
        s = re.sub(r"(?is)<.*?>", "", s)
        return re.sub(r"\n{3,}", "\n\n", s).strip()

    return [_html_to_text(h) for h in html if h]


def _has_attachments(msg: email.message.Message) -> bool:
    for part in msg.walk():
        if (part.get_content_disposition() or "").lower() == "attachment":
            return True
    return False


def _connect() -> imaplib.IMAP4_SSL:
    # 読取専用で使うための SSL 接続作成（認証は select 前後で行う）
    return imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)


def _search_uids(m: imaplib.IMAP4_SSL, args) -> list[bytes]:
    # 既定は UNSEEN（未読）
    criteria = ["UNSEEN"]
    if args.all:
        criteria = ["ALL"]

    # 期間指定（since / days はどちらか片方を想定）
    if args.since:
        d = dt.datetime.strptime(args.since, "%Y-%m-%d").strftime("%d-%b-%Y")
        criteria += ["SINCE", d]
    elif args.days is not None:
        base = dt.datetime.now() - dt.timedelta(days=args.days)
        d = base.strftime("%d-%b-%Y")
        criteria += ["SINCE", d]

    # SEARCH 実行
    typ, data = m.uid("SEARCH", None, *criteria)
    if typ != "OK":
        raise RuntimeError(f"SEARCH 失敗: {typ} {data}")
    raw = data[0] or b""
    uids = raw.split()
    # 新しいものから処理
    uids.reverse()
    if args.limit and len(uids) > args.limit:
        uids = uids[:args.limit]
    return uids


def _save_text(uid: bytes, msg: email.message.Message) -> str:
    d = _message_datetime(msg)
    subj = _decode_header(msg.get("Subject"))
    frm = _decode_header(msg.get("From"))
    has_att = _has_attachments(msg)
    body_parts = list(_iter_text_parts(msg))
    body = "\n\n".join(body_parts).strip()

    file_stem = f"{d.strftime('%Y%m%d_%H%M%S')}_UID{uid.decode()}"
    path = path_for_mail_text(file_stem)

    header_block = [
        f"UID: {uid.decode()}",
        f"Date: {d.isoformat(sep=' ', timespec='seconds')}",
        f"From: {frm}",
        f"Subject: {subj}",
        f"Attachments: {has_att}",
        "-" * 60,
        "",
    ]
    text = "\n".join(header_block) + body + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return str(path)


def main():
    require_ready()

    ap = argparse.ArgumentParser(description="IMAP フェッチ → テキスト保存")
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--all", action="store_true", help="ALL（既読/未読すべて）で検索")
    ap.add_argument("--since", type=str, help="この日付以降 (YYYY-MM-DD)")
    ap.add_argument("--days", type=int, help="直近N日 (例: --days 3)")
    ap.add_argument("--limit", type=int, default=20, help="最大取得件数（新しい順）")
    ap.add_argument("--dry-run", action="store_true", help="保存せず対象のみ一覧表示")
    args = ap.parse_args()

    with _connect() as m:
        # ログイン & メールボックス選択（READ-ONLY 固定：副作用なし）
        m.login(IMAP_USER, IMAP_PASS)
        typ, _ = m.select(IMAP_MAILBOX, readonly=True)
        if typ != "OK":
            raise RuntimeError(f"メールボックス選択に失敗: {IMAP_MAILBOX}")

        uids = _search_uids(m, args)
        print(f"検索条件: all={args.all}, since={args.since}, days={args.days}, limit={args.limit}")
        print(f"対象UID数: {len(uids)}")

        saved = 0
        for uid in uids:
            typ, data = m.uid("FETCH", uid, "(RFC822)")
            if typ != "OK" or not data or not isinstance(data[0], tuple):
                print(f"[SKIP] FETCH失敗 uid={uid} resp={typ}")
                continue

            raw = data[0][1]
            msg = email.message_from_bytes(raw, policy=email.policy.default)

            # --- dry-run 表示のみ ---
            if args.dry_run:
                d = _message_datetime(msg)
                subj = _decode_header(msg.get("Subject"))
                frm = _decode_header(msg.get("From"))
                print(f"[DRY] {d:%Y-%m-%d %H:%M:%S} UID={uid.decode()} From={frm} Subj={subj}")
                # dry-runでもフィルタ結果を見たい場合は以下を解除
                # res = filter_message(msg, FILTER_CONF)
                # print(f"       -> filter: pass={res.pass_through} reason={res.reason} detail={res.detail}")
                continue

            # === ここからフィルタリング（保存前に判定） ===
            res = filter_message(msg, FILTER_CONF)
            if not res.pass_through:
                # 除外：保存も次工程も行わない
                # 画面にも軽く出しておくと確認が楽です（ログは filters 側で出ます）
                print(f"[DROP] UID={uid.decode()} reason={res.reason} detail={res.detail} Subj={_decode_header(msg.get('Subject'))}")
                continue
            # === フィルタ通過：案件メールのみ保存 ===

            p = _save_text(uid, msg)
            print(f"[SAVE] {p}")
            saved += 1

        print(f"保存件数: {saved}")


if __name__ == "__main__":
    main()
