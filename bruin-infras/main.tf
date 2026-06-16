terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "5.6.0"
    }
  }
}

provider "google" {
  credentials = file(var.credentials)
  project     = var.project
  region      = var.region
}


resource "google_storage_bucket" "bruin_bucket_mod5" {
  name          = var.gcs_bucket_name
  location      = var.location
  force_destroy = true


  lifecycle_rule {
    condition {
      age = 1
    }
    action {
      type = "AbortIncompleteMultipartUpload"
    }
  }
}



resource "google_bigquery_dataset" "ingestion" {
  dataset_id = var.bq_ingestion_dataset_name
  location   = var.location
}

resource "google_bigquery_dataset" "staging" {
  dataset_id = var.bq_staging_dataset_name
  location   = var.location
}

resource "google_bigquery_dataset" "reports" {
  dataset_id = var.bq_reports_dataset_name
  location   = var.location
}