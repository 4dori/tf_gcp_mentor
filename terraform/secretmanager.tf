# Secret container only — the actual connection-string value is NEVER stored in Terraform.
# After `terraform apply`, add the value with:
#   gcloud secrets versions add cloud-sql-connection-string \
#     --data-file=<(echo "host=HOST;user=pipeline-reader;password=PASS;dbname=adventureworks")
# Never commit the real value to git.

resource "google_secret_manager_secret" "cloud_sql_conn" {
  secret_id = "cloud-sql-connection-string"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

# sa-dataproc-jobs: read the secret at runtime
resource "google_secret_manager_secret_iam_member" "dataproc_jobs_secret_access" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.cloud_sql_conn.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.dataproc_jobs.email}"
}
