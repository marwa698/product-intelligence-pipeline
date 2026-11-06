import os
import logging
import requests
from sqlalchemy import text

log = logging.getLogger(__name__)


def send_alert(message: str) -> bool:
    """Send a Telegram message. If it fails, log only and never crash the pipeline."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.warning("Telegram not configured; alert skipped: %s", message)
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": message},
            timeout=10,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        log.error("Could not send alert: %s", e)
        return False


def task_failure_alert(context):
    """Airflow callback: runs after the last failed retry of a task."""
    ti = context["task_instance"]
    send_alert(
        f"Pipeline task failed\n"
        f"DAG: {ti.dag_id}\nTask: {ti.task_id}\n"
        f"Run: {context.get('run_id')}\nTries: {ti.try_number}"
    )


def check_price_alerts(engine, threshold=None):
    """Send one alert with the biggest price changes in the latest snapshot."""
    threshold = float(threshold or os.getenv("PRICE_ALERT_THRESHOLD", 20))
    sql = text("""
        SELECT product_name, old_price, new_price, pct_change
        FROM v_price_changes
        WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM price_history)
          AND ABS(pct_change) >= :t
        ORDER BY ABS(pct_change) DESC
        LIMIT 10
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"t": threshold}).fetchall()
    if rows:
        lines = [f"- {r[0]}: {r[1]} -> {r[2]} ({r[3]}%)" for r in rows]
        send_alert(f"Price moves >= {threshold}% in the latest snapshot:\n" + "\n".join(lines))
    return len(rows)