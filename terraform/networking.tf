data "google_compute_network" "default" {
  name    = "default"
  project = var.project_id
}

data "google_compute_subnetwork" "default" {
  name    = "default"
  region  = var.region
  project = var.project_id
}

resource "google_compute_address" "dataproc_nat" {
  name         = "dataproc-cloud-nat-ip"
  address_type = "EXTERNAL"
  network_tier = "PREMIUM"
  region       = var.region
  project      = var.project_id

  depends_on = [google_project_service.apis]
}

resource "google_compute_router" "dataproc" {
  name    = "dataproc-cloud-router"
  network = data.google_compute_network.default.self_link
  region  = var.region
  project = var.project_id

  bgp {
    asn = 64514
  }

  depends_on = [google_project_service.apis]
}

resource "google_compute_router_nat" "dataproc" {
  name                               = "dataproc-cloud-nat"
  router                             = google_compute_router.dataproc.name
  region                             = var.region
  project                            = var.project_id
  nat_ip_allocate_option             = "MANUAL_ONLY"
  nat_ips                            = [google_compute_address.dataproc_nat.self_link]
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"

  subnetwork {
    name                    = data.google_compute_subnetwork.default.self_link
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }
}

resource "google_compute_subnetwork_iam_member" "dataproc_network_user" {
  project    = var.project_id
  region     = var.region
  subnetwork = data.google_compute_subnetwork.default.name
  role       = "roles/compute.networkUser"
  member     = "serviceAccount:${google_service_account.dataproc_jobs.email}"
}