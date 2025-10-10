# src/jobs/scheduler.py
import os
import time
import subprocess
import sys
from datetime import datetime
from loguru import logger
import schedule

# ===== 設定 =====
# 本番スケジュール（JST）
SCHEDULE_TIMES = ["10:00", "13:00", "16:00"]

# テストモード：True にすると毎分実行（まずは True で動作確認をおすすめ）
TEST_MODE = True
# =================

# ログ設定（logs/ にローテーション保存）
os.makedirs("logs", exist_ok=True)
logger.add("logs/scheduler.log", rotation="1 week", retention="4 weeks", encoding="utf-8")

def run_imap_fetch():
    """既存の imap_fetch.py を -m で起動"""
    logger.info("[scheduler] imap_fetch を起動します")
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "src.jobs.imap_fetch"],
            capture_output=True,
            text=True,
            check=False  # 失敗してもスケジューラ自体は止めない
        )
        logger.info(f"[scheduler] imap_fetch 終了 (returncode={completed.returncode})")
        if completed.stdout:
            logger.debug(f"[imap_fetch stdout]\n{completed.stdout}")
        if completed.stderr:
            logger.warning(f"[imap_fetch stderr]\n{completed.stderr}")
    except Exception as e:
        logger.exception(f"[scheduler] imap_fetch 実行中に例外: {e}")

def main():
    logger.info("=== スケジューラ起動 ===")
    logger.info(f"起動時刻: {datetime.now().isoformat(timespec='seconds')}")

    if TEST_MODE:
        logger.warning("TEST_MODE=True: 毎分 imap_fetch を実行します（動作確認用）")
        schedule.every(1).minutes.do(run_imap_fetch)
    else:
        for t in SCHEDULE_TIMES:
            schedule.every().day.at(t).do(run_imap_fetch)
            logger.info(f"スケジュール登録: 毎日 {t} に imap_fetch 実行")

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Ctrl+C でスケジューラを停止しました。")
    finally:
        logger.info("=== スケジューラ停止 ===")

if __name__ == "__main__":
    main()
