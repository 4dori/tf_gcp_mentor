output "landing_bucket" {
  description = "GCS URI of the landing bucket for raw ingestion files."
  value       = "gs://${google_storage_bucket.landing.name}"
}

output "deploy_bucket" {
  description = "GCS URI of the deploy bucket for job scripts, JDBC jar, and workflow YAML."
  value       = "gs://${google_storage_bucket.deploy.name}"
}

output "warehouse_dataset" {
  description = "Full BigQuery dataset ID."
  value       = "${var.project_id}.${google_bigquery_dataset.warehouse.dataset_id}"
}

output "sa_dataproc_jobs_email" {
  description = "Email of the Dataproc batch runner service account."
  value       = google_service_account.dataproc_jobs.email
}

output "sa_cloudbuild_email" {
  description = "Email of the Cloud Build CI/CD service account."
  value       = google_service_account.cloudbuild.email
}

output "sa_workflows_email" {
  description = "Email of the Cloud Workflows orchestrator service account."
  value       = google_service_account.workflows.email
}

output "cloud_sql_secret_id" {
  description = "Resource ID of the Cloud SQL connection-string secret container."
  value       = google_secret_manager_secret.cloud_sql_conn.id
}
