import sys
import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

sys.path.append("/opt/airflow")  # so Airflow can find the scraper and etl folders

log = logging.getLogger(__name__)


def _task_failure_alert(context):
    from etl.alerts import task_failure_alert
    task_failure_alert(context)


default_args = {
    "owner": "team",
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "on_failure_callback": _task_failure_alert,
}


def task_scrape(**context):
    from scraper.scrape_products import main
    path = main()  # must return the raw file path
    context["ti"].xcom_push(key="raw_path", value=path)


def task_validate(**context):
    from etl.clean import validate_raw
    validate_raw(context["ti"].xcom_pull(task_ids="scrape", key="raw_path"))


def task_clean(**context):
    from etl.clean import run_cleaning
    ti = context["ti"]
    clean_path, rejected_path = run_cleaning(
        ti.xcom_pull(task_ids="scrape", key="raw_path")
    )
    ti.xcom_push(key="clean_path", value=clean_path)
    ti.xcom_push(key="rejected_path", value=rejected_path)


def task_dedup(**context):
    from etl.dedup import run_dedup
    ti = context["ti"]
    dedup_path = run_dedup(ti.xcom_pull(task_ids="clean", key="clean_path"))
    ti.xcom_push(key="dedup_path", value=dedup_path)


def task_load(**context):
    from etl.load import run_load
    ti = context["ti"]
    n = run_load(ti.xcom_pull(task_ids="dedup", key="dedup_path"))
    ti.xcom_push(key="rows_loaded", value=n)
    log.info("Loaded %s rows", n)


def task_run_analysis(**context):
    from sqlalchemy import text
    from etl.db import get_engine
    from etl.alerts import check_price_alerts

    engine = get_engine()
    with engine.connect() as conn:
        for view in ["v_price_changes", "v_new_products",
                     "v_removed_products", "v_category_changes"]:
            n = conn.execute(text(f"SELECT COUNT(*) FROM {view}")).scalar()
            log.info("%s: %s rows", view, n)
    check_price_alerts(engine)


def task_quality_check(**context):
    from etl.quality_checks import run_quality_checks
    ti = context["ti"]
    run_quality_checks(
        ti.xcom_pull(task_ids="scrape", key="raw_path"),
        ti.xcom_pull(task_ids="clean", key="clean_path"),
        ti.xcom_pull(task_ids="clean", key="rejected_path"),
    )
    from etl.run_log import write_run_log_from_task
    write_run_log_from_task(ti, context["dag_run"], "success")




with DAG(
    dag_id="product_intelligence_pipeline",
    default_args=default_args,
    description="Scrape -> Clean -> Dedup -> Load -> Analyze -> Quality Check",
    start_date=datetime(2026, 10, 1),
    schedule="@daily",
    catchup=False,
    tags=["capstone", "etl"],

   
) as dag:
    scrape = PythonOperator(task_id="scrape", python_callable=task_scrape)
    validate = PythonOperator(task_id="validate", python_callable=task_validate)
    clean = PythonOperator(task_id="clean", python_callable=task_clean)
    dedup = PythonOperator(task_id="dedup", python_callable=task_dedup)
    load = PythonOperator(task_id="load", python_callable=task_load)
    run_analysis = PythonOperator(task_id="run_analysis", python_callable=task_run_analysis)
    quality_check = PythonOperator(task_id="quality_check", python_callable=task_quality_check)

    scrape >> validate >> clean >> dedup >> load >> run_analysis >> quality_check