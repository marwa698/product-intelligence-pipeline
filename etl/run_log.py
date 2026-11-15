import logging
from datetime import datetime

import pandas as pd
from sqlalchemy import text

from etl.db import get_engine

log = logging.getLogger(__name__)


def _xcom(dag_run, task_id, key):
    ti = dag_run.get_task_instance(task_id)
    return ti.xcom_pull(task_ids=task_id, key=key) if ti else None


def _count_rows(path, is_json=False):
    try:
        return len(pd.read_json(path)) if is_json else len(pd.read_csv(path))
    except Exception:
        return None


def write_run_log(context, status):
    """Called from the DAG-level on_success/on_failure callback."""
    try:
        dr = context["dag_run"]
        end = datetime.now()
        start = dr.start_date.replace(tzinfo=None) if dr.start_date else end
        raw = _xcom(dr, "scrape", "raw_path")
        rejected = _xcom(dr, "clean", "rejected_path")
        row = {
            "dag_run_id": dr.run_id,
            "start_time": start,
            "end_time": end,
            "duration_sec": int((end - start).total_seconds()),
            "status": status,
            "rows_scraped": _count_rows(raw, is_json=True) if raw else None,
            "rows_loaded": _xcom(dr, "load", "rows_loaded"),
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
        # logging must never break the pipeline
        log.error("Could not write pipeline_run_log: %s", e)