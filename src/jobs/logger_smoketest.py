# src/jobs/logger_smoketest.py
from datetime import datetime
from src.config import LOG_DIR
from src.common.logging_setup import setup_logger

def run() -> int:
    log_path = LOG_DIR / f"logger_smoketest_{datetime.now().strftime('%Y%m%d')}.log"
    logger = setup_logger(log_path)

    logger.info("ロガースモークテスト開始")
    logger.warning("これは WARNING のサンプルです")
    logger.error("これは ERROR のサンプルです（動作確認用）")
    logger.info("ロガースモークテスト完了")
    return 0

if __name__ == "__main__":
    raise SystemExit(run())
