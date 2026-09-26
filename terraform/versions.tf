terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "project-3bb39664-085c-42fe-811-tf-state"
    prefix = "mentoring-program"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
