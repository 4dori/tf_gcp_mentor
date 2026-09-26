# ── Project-level IAM bindings ────────────────────────────────────────────────

# sa-dataproc-jobs: BigQuery Data Editor (to write tables)
resource "google_project_iam_member" "dataproc_jobs_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.dataproc_jobs.email}"
}

# sa-dataproc-jobs: BigQuery Job User (to run jobs)
resource "google_project_iam_member" "dataproc_jobs_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.dataproc_jobs.email}"
}

# sa-dataproc-jobs: Dataproc Worker (runtime identity for batches)
resource "google_project_iam_member" "dataproc_jobs_worker" {
  project = var.project_id
  role    = "roles/dataproc.worker"
  member  = "serviceAccount:${google_service_account.dataproc_jobs.email}"
}

# sa-workflows: Dataproc Editor (to call batches.create / batches.get)
resource "google_project_iam_member" "workflows_dataproc_editor" {
  project = var.project_id
  role    = "roles/dataproc.editor"
  member  = "serviceAccount:${google_service_account.workflows.email}"
}

# sa-cloudbuild: minimum project-level roles needed to run terraform apply
# Add more specific roles if tf apply reports missing permissions — do NOT grant Editor.
resource "google_project_iam_member" "cloudbuild_service_account_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.cloudbuild.email}"
}

resource "google_project_iam_member" "cloudbuild_service_usage_consumer" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageConsumer"
  member  = "serviceAccount:${google_service_account.cloudbuild.email}"
}

# Bucket-level IAM bindings are in storage.tf
