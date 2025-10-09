# src/jobs/imap_check.py
import imaplib
from datetime import datetime

from src.config import (
    IMAP_HOST, IMAP_PORT, IMAP_USER, IMAP_PASS, IMAP_MAILBOX, LOG_DIR, require_ready
)
from src.common.logging_setup import setup_logger


def run() -> int:
    # 前提条件チェック（.envや保存先ディレクトリが有効か）
    require_ready()

    # ログファイル名：例）data/mail_archive/logs/imap_check_20251008.log
    log_path = LOG_DIR / f"imap_check_{datetime.now().strftime('%Y%m%d')}.log"
    logger = setup_logger(log_path)
    logger.info("IMAP 接続スモークテスト開始")

    imap = None
    try:
        # 1) サーバーにSSLで接続（993）
        imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        logger.info(f"接続OK: {IMAP_HOST}:{IMAP_PORT}")

        # 2) ログイン
        typ, _ = imap.login(IMAP_USER, IMAP_PASS)
        if typ != "OK":
            logger.error(f"ログインNG（typ={typ}）")
            return 2
        logger.info(f"ログインOK: {IMAP_USER}")

        # 3) メールボックス選択（読み取り専用）
        typ, _ = imap.select(IMAP_MAILBOX, readonly=True)
        if typ != "OK":
            logger.error(f"メールボックス選択NG: {IMAP_MAILBOX}（typ={typ}）")
            return 2
        logger.info(f"メールボックス選択OK（readonly）: {IMAP_MAILBOX}")

        # ここでは本文取得などは「一切しない」＝接続確認のみ
        return 0

    except imaplib.IMAP4.error as e:
        logger.exception(f"IMAP 認証/コマンドエラー: {e!r}")
        return 2
    except Exception as e:
        logger.exception(f"IMAP 接続失敗: {e!r}")
        return 2
    finally:
        # 後片付け（close→logout）
        try:
            if imap is not None:
                try:
                    imap.close()
                except Exception:
                    pass  # select前にcloseすると例外のことがあるため握りつぶし
                imap.logout()
                logger.info("IMAP セッションをクローズしました")
        except Exception:
            pass
        logger.info("IMAP 接続スモークテスト終了")


if __name__ == "__main__":
    raise SystemExit(run())
