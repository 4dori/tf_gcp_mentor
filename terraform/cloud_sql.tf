resource "google_sql_database_instance" "adventureworks" {
  name                = "adventureworks-db"
  project             = var.project_id
  region              = var.region
  database_version    = "POSTGRES_15"
  deletion_protection = true

  settings {
    tier                        = "db-custom-2-8192"
    edition                     = "ENTERPRISE"
    availability_type           = "ZONAL"
    activation_policy           = "ALWAYS"
    disk_size                   = 10
    disk_type                   = "PD_SSD"
    disk_autoresize             = true
    disk_autoresize_limit       = 0
    deletion_protection_enabled = true
    connector_enforcement       = "NOT_REQUIRED"
    enable_dataplex_integration = true

    backup_configuration {
      enabled                        = false
      start_time                     = "13:00"
      transaction_log_retention_days = 7

      backup_retention_settings {
        retained_backups = 7
        retention_unit   = "COUNT"
      }
    }

    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "ALLOW_UNENCRYPTED_AND_ENCRYPTED"

      authorized_networks {
        name  = "dataproc-cloud-nat"
        value = "${google_compute_address.dataproc_nat.address}/32"
      }
    }

    location_preference {
      zone = "us-central1-a"
    }
  }

  lifecycle {
    prevent_destroy = true
  }

  depends_on = [
    google_project_service.apis,
    google_compute_router_nat.dataproc,
  ]
}

resource "google_sql_database" "adventureworks" {
  name      = "adventureworks"
  project   = var.project_id
  instance  = google_sql_database_instance.adventureworks.name
  charset   = "UTF8"
  collation = "en_US.UTF8"

  lifecycle {
    prevent_destroy = true
  }
}