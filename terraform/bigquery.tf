resource "google_bigquery_dataset" "warehouse" {
  dataset_id  = "warehouse"
  location    = var.region
  description = "Fact/dim tables for both the Airbnb and AdventureWorks lanes"
  project     = var.project_id

  depends_on = [google_project_service.apis]
}

# Tables (airbnb_fact_listings, sales_fact, sales_dim) are created at runtime
# by PySpark jobs writing via the Spark BigQuery connector — NOT managed by Terraform.
