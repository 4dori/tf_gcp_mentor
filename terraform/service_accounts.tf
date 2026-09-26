# ── sa-dataproc-jobs ──────────────────────────────────────────────────────────
resource "google_service_account" "dataproc_jobs" {
  account_id   = "sa-dataproc-jobs"
  display_name = "Dataproc PySpark batch runner"
  description  = "Used by Dataproc Serverless batches to read from GCS and write to BigQuery."
  project      = var.project_id

  depends_on = [google_project_service.apis]
}

# ── sa-cloudbuild ─────────────────────────────────────────────────────────────
resource "google_service_account" "cloudbuild" {
  account_id   = "sa-cloudbuild"
  display_name = "Cloud Build CI/CD"
  description  = "Used by Cloud Build to run terraform apply and copy job artifacts to GCS."
  project      = var.project_id

  depends_on = [google_project_service.apis]
}

# ── sa-workflows ──────────────────────────────────────────────────────────────
resource "google_service_account" "workflows" {
  account_id   = "sa-workflows"
  display_name = "Cloud Workflows orchestrator"
  description  = "Used by Cloud Workflows to submit and poll Dataproc Serverless batches."
  project      = var.project_id

  depends_on = [google_project_service.apis]
}
