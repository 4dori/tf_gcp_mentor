# ── Buckets ───────────────────────────────────────────────────────────────────

resource "google_storage_bucket" "landing" {
  name                        = "${var.project_id}-landing"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true # convenience for a learning project; drop this for anything real

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket" "deploy" {
  name                        = "${var.project_id}-deploy"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true # convenience for a learning project; drop this for anything real

  depends_on = [google_project_service.apis]
}

# ── Bucket-level IAM bindings ─────────────────────────────────────────────────

# sa-dataproc-jobs → objectAdmin on the landing bucket (reads raw files, writes curated)
resource "google_storage_bucket_iam_member" "dataproc_jobs_landing" {
  bucket = google_storage_bucket.landing.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.dataproc_jobs.email}"
}

# sa-cloudbuild → objectAdmin on the deploy bucket (copies job scripts and JDBC jar)
resource "google_storage_bucket_iam_member" "cloudbuild_deploy" {
  bucket = google_storage_bucket.deploy.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.cloudbuild.email}"
}

# sa-dataproc-jobs → objectAdmin on the deploy bucket (reads job scripts and JDBC jar at runtime)
resource "google_storage_bucket_iam_member" "dataproc_jobs_deploy_read" {
  bucket = google_storage_bucket.deploy.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.dataproc_jobs.email}"
}
