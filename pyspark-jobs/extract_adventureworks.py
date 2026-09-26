"""
Lane B — Job 1
Read AdventureWorks tables from Cloud SQL (Postgres) via JDBC and write as Parquet.

The connection string is fetched from Secret Manager at runtime — never hardcoded.
Connection string format stored in the secret:
  host=HOST;user=pipeline-reader;password=PASS;dbname=adventureworks

Submit example:
  gcloud dataproc batches submit pyspark gs://$PROJECT-deploy/jobs/extract_adventureworks.py \
    --region=us-central1 \
    --service-account=sa-dataproc-jobs@$PROJECT.iam.gserviceaccount.com \
    --deps-bucket=gs://$PROJECT-deploy \
    --jars=gs://$PROJECT-deploy/jars/postgresql-42.7.3.jar \
    -- --project=$PROJECT
"""

import argparse
import os
import sys

import google.auth
from google.cloud import secretmanager
from pyspark.sql import SparkSession

SECRET_NAME_TEMPLATE = "projects/{project}/secrets/cloud-sql-connection-string/versions/latest"

TABLES = [
    "sales.salesorderheader",
    "sales.salesorderdetail",
    "sales.product",
    "sales.customer",
]


def parse_args():
    _, default_project = google.auth.default()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project",
        default=os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT") or default_project,
        help="GCP project ID (defaults to the Dataproc project environment)",
    )
    return parser.parse_args()


def get_secret(project: str) -> dict:
    client = secretmanager.SecretManagerServiceClient()
    name = SECRET_NAME_TEMPLATE.format(project=project)
    response = client.access_secret_version(request={"name": name})
    raw = response.payload.data.decode("utf-8")
    # Parse key=value;key=value format
    return dict(pair.split("=", 1) for pair in raw.split(";") if "=" in pair)


def main():
    args = parse_args()
    if not args.project:
        raise ValueError("GCP project ID is required via --project or GOOGLE_CLOUD_PROJECT")
    conn = get_secret(args.project)

    host = conn["host"]
    user = conn["user"]
    password = conn["password"]
    dbname = conn.get("dbname", "adventureworks")

    jdbc_url = f"jdbc:postgresql://{host}/{dbname}"
    jdbc_props = {
        "user": user,
        "password": password,
        "driver": "org.postgresql.Driver",
    }

    curated_base = f"gs://{args.project}-landing/curated/adventureworks"

    spark = SparkSession.builder.appName("extract_adventureworks").getOrCreate()

    for table in TABLES:
        df = spark.read.jdbc(url=jdbc_url, table=table, properties=jdbc_props)
        table_safe = table.replace(".", "_")
        out = f"{curated_base}/{table_safe}"
        df.write.mode("overwrite").parquet(out)
        print(f"Extracted {df.count()} rows from {table} → {out}")

    spark.stop()


if __name__ == "__main__":
    main()
