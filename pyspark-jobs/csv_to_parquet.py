"""
Lane A — Job 1
Read Airbnb CSV files from GCS landing bucket and write as Parquet to curated layer.

Submit example:
  gcloud dataproc batches submit pyspark gs://$PROJECT-deploy/jobs/csv_to_parquet.py \
    --region=us-central1 \
    --service-account=sa-dataproc-jobs@$PROJECT.iam.gserviceaccount.com \
    --deps-bucket=gs://$PROJECT-deploy \
    -- --project=$PROJECT
"""

import argparse
import os
import sys

import google.auth
from pyspark.sql import SparkSession

EXPECTED_COLUMNS = {
    "listings": ["id", "name", "host_id", "neighbourhood", "latitude", "longitude",
                 "room_type", "price", "minimum_nights", "number_of_reviews",
                 "last_review", "reviews_per_month", "calculated_host_listings_count",
                 "availability_365"],
    "calendar": ["listing_id", "date", "available", "price"],
    "reviews":  ["listing_id", "id", "date", "reviewer_id", "reviewer_name", "comments"],
}


def parse_args():
    _, default_project = google.auth.default()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project",
        default=os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT") or default_project,
        help="GCP project ID (defaults to the Dataproc project environment)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.project:
        raise ValueError("GCP project ID is required via --project or GOOGLE_CLOUD_PROJECT")
    landing = f"gs://{args.project}-landing"
    curated = f"gs://{args.project}-landing/curated/airbnb"

    spark = SparkSession.builder.appName("csv_to_parquet").getOrCreate()

    for name in ["listings", "calendar", "reviews"]:
        path = f"{landing}/raw/airbnb/{name}.csv"
        df = (
            spark.read.option("header", "true")
            .option("multiLine", "true")
            .option("escape", '"')
            .csv(path)
        )

        # Validate expected columns exist
        missing = set(EXPECTED_COLUMNS[name]) - set(df.columns)
        if missing:
            print(f"ERROR: {name}.csv is missing columns: {missing}", file=sys.stderr)
            sys.exit(1)

        out = f"{curated}/{name}"
        df.write.mode("overwrite").parquet(out)
        print(f"Written {df.count()} rows → {out}")

    spark.stop()


if __name__ == "__main__":
    main()
