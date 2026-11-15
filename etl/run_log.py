import logging
from datetime import datetime

import pandas as pd
from sqlalchemy import text

from etl.db import get_engine

log = logging.getLogger(__name__)


def _count_rows(path, is_json=False):
    try:
        return len(pd.read_json(path)) if is_json else len(pd.read_csv(path))
    except Exception:
        return None


def write_run_log_from_task(ti, dag_run, status="success"):
    try:
        end = datetime.now()
        start = dag_run.start_date.replace(tzinfo=None) if dag_run.start_date else end
        raw = ti.xcom_pull(task_ids="scrape", key="raw_path")
        rejected = ti.xcom_pull(task_ids="clean", key="rejected_path")
        row = {
            "dag_run_id": dag_run.run_id,
            "start_time": start,
            "end_time": end,
            "duration_sec": int((end - start).total_seconds()),
            "status": status,
            "rows_scraped": _count_rows(raw, is_json=True) if raw else None,
            "rows_loaded": ti.xcom_pull(task_ids="load", key="rows_loaded"),
            "rows_rejected": _count_rows(rejected) if rejected else None,
        }
        with get_engine().begin() as conn:
            conn.execute(text("""
                INSERT INTO pipeline_run_log
                (dag_run_id, start_time, end_time, duration_sec, status,
                 rows_scraped, rows_loaded, rows_rejected)
                VALUES (:dag_run_id, :start_time, :end_time, :duration_sec, :status,
                        :rows_scraped, :rows_loaded, :rows_rejected)
            """), row)
    except Exception as e:
        log.error("Could not write pipeline_run_log: %s", e)
