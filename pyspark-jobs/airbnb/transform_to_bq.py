"""
Lane A — Job 2
Read curated Airbnb Parquet from GCS and write fact table to BigQuery.

Submit example:
    gcloud dataproc batches submit pyspark gs://$PROJECT-deploy/jobs/airbnb/transform_to_bq.py \
    --region=us-central1 \
    --service-account=sa-dataproc-jobs@$PROJECT.iam.gserviceaccount.com \
    --deps-bucket=gs://$PROJECT-deploy \
    -- --project=$PROJECT
"""

import argparse
import os
import re
import sys

import google.auth
from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def parse_args():
    _, default_project = google.auth.default()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project",
        default=os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT") or default_project,
        help="GCP project ID (defaults to the Dataproc project environment)",
    )
    return parser.parse_args()


def clean_price(col):
    """Strip $ and commas, cast to double."""
    return F.regexp_replace(F.regexp_replace(col, r"\$", ""), ",", "").cast("double")


def main():
    args = parse_args()
    if not args.project:
        raise ValueError("GCP project ID is required via --project or GOOGLE_CLOUD_PROJECT")
    curated = f"gs://{args.project}-landing/curated/airbnb/listings"
    deploy_bucket = f"{args.project}-deploy"
    bq_table = f"{args.project}.warehouse.airbnb_fact_listings"

    spark = SparkSession.builder.appName("transform_to_bq").getOrCreate()

    df = spark.read.parquet(curated)

    # Clean price field
    df = df.withColumn("price_usd", clean_price(F.col("price")))

    fact_cols = [
        "id", "host_id", "neighbourhood", "latitude", "longitude",
        "room_type", "price_usd", "minimum_nights", "number_of_reviews",
        "last_review", "reviews_per_month", "calculated_host_listings_count",
        "availability_365",
    ]
    fact = df.select(*fact_cols)

    # Assertions before writing
    row_count = fact.count()
    if row_count == 0:
        print("ERROR: fact table has 0 rows — aborting.", file=sys.stderr)
        sys.exit(1)

    null_ids = fact.filter(F.col("id").isNull()).count()
    if null_ids > 0:
        print(f"ERROR: {null_ids} rows with null id — aborting.", file=sys.stderr)
        sys.exit(1)

    print(f"Writing {row_count} rows → {bq_table}")

    (
        fact.write.format("bigquery")
        .option("table", bq_table)
        .option("temporaryGcsBucket", deploy_bucket)
        .mode("overwrite")
        .save()
    )

    print("Done.")
    spark.stop()


if __name__ == "__main__":
    main()
