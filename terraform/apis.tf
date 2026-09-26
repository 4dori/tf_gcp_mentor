locals {
  apis = [
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "storage.googleapis.com",
    "bigquery.googleapis.com",
    "dataproc.googleapis.com",
    "secretmanager.googleapis.com",
    "billingbudgets.googleapis.com",
    "workflows.googleapis.com",
    "cloudbuild.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each = toset(local.apis)

  project                    = var.project_id
  service                    = each.value
  disable_dependent_services = false
  disable_on_destroy         = false
}
