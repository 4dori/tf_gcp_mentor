"""
Lane B — Job 2
Read curated AdventureWorks Parquet and write sales_fact + sales_dim to BigQuery.

Submit example:
  gcloud dataproc batches submit pyspark gs://$PROJECT-deploy/jobs/transform_adventureworks.py \
    --region=us-central1 \
    --service-account=sa-dataproc-jobs@$PROJECT.iam.gserviceaccount.com \
    --deps-bucket=gs://$PROJECT-deploy \
    --properties spark.jars.packages=com.google.cloud.spark:spark-bigquery-with-dependencies_2.12:0.36.1 \
    -- --project=$PROJECT
"""

import argparse
import os
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


def write_bq(df, table: str, deploy_bucket: str):
    row_count = df.count()
    if row_count == 0:
        print(f"ERROR: {table} has 0 rows — aborting.", file=sys.stderr)
        sys.exit(1)
    null_check_col = df.columns[0]
    null_ids = df.filter(F.col(null_check_col).isNull()).count()
    if null_ids > 0:
        print(f"ERROR: {null_ids} rows with null {null_check_col} in {table} — aborting.",
              file=sys.stderr)
        sys.exit(1)
    print(f"Writing {row_count} rows → {table}")
    (
        df.write.format("bigquery")
        .option("table", table)
        .option("temporaryGcsBucket", deploy_bucket)
        .mode("overwrite")
        .save()
    )


def main():
    args = parse_args()
    if not args.project:
        raise ValueError("GCP project ID is required via --project or GOOGLE_CLOUD_PROJECT")
    curated = f"gs://{args.project}-landing/curated/adventureworks"
    deploy_bucket = f"{args.project}-deploy"
    dataset = f"{args.project}.warehouse"

    spark = SparkSession.builder.appName("transform_adventureworks").getOrCreate()

    orders = spark.read.parquet(f"{curated}/sales_salesorderheader")
    details = spark.read.parquet(f"{curated}/sales_salesorderdetail")
    products = spark.read.parquet(f"{curated}/sales_product")
    customers = spark.read.parquet(f"{curated}/sales_customer")

    # ── Detailed sales fact ───────────────────────────────────────────────────
    sales_fact = (
        details.alias("d")
        .join(orders.alias("o"), F.col("d.salesorderid") == F.col("o.salesorderid"))
        .join(products.alias("p"), F.col("d.productid") == F.col("p.productid"))
        .join(customers.alias("c"), F.col("o.customerid") == F.col("c.customerid"))
        .select(
            F.col("d.salesorderid"),
            F.col("d.salesorderdetailid"),
            F.col("o.orderdate").cast("date").alias("order_date"),
            F.col("o.customerid"),
            F.col("c.storeid"),
            F.col("d.productid"),
            F.col("p.name").alias("product_name"),
            F.col("p.productcategoryid"),
            F.col("d.orderqty"),
            F.col("d.unitprice"),
            F.col("d.linetotal"),
        )
    )

    write_bq(sales_fact, f"{dataset}.sales_fact", deploy_bucket)

    # ── Aggregate dim (day / month / product) ────────────────────────────────
    sales_dim = (
        sales_fact
        .withColumn("order_month", F.date_trunc("month", F.col("order_date")))
        .groupBy("order_date", "order_month", "productid", "product_name")
        .agg(
            F.sum("linetotal").alias("total_revenue"),
            F.sum("orderqty").alias("total_qty"),
            F.countDistinct("salesorderid").alias("order_count"),
        )
    )

    write_bq(sales_dim, f"{dataset}.sales_dim", deploy_bucket)

    print("Done.")
    spark.stop()


if __name__ == "__main__":
    main()
