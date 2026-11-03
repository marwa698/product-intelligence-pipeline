from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.empty import EmptyOperator

default_args = {
    "owner": "team",
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="product_intelligence_pipeline",
    default_args=default_args,
    start_date=datetime(2026, 10, 1),
    schedule="@daily",
    catchup=False,
    tags=["capstone", "etl"],
) as dag:
    names = ["scrape", "validate", "clean", "dedup", "load", "run_analysis", "quality_check"]
    tasks = [EmptyOperator(task_id=n) for n in names]

    for a, b in zip(tasks, tasks[1:]):
        a >> b