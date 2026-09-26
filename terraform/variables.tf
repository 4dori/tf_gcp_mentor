variable "project_id" {
  description = "GCP project ID where all resources will be created."
  type        = string
}

variable "region" {
  description = "Default GCP region for all regional resources."
  type        = string
  default     = "us-central1"
}

variable "billing_account_id" {
  description = "Billing account ID in the format XXXXXX-XXXXXXXXXX (required for budget alert)."
  type        = string
}

variable "budget_amount_usd" {
  description = "Monthly spend threshold in USD for the billing budget."
  type        = number
  default     = 50
}
