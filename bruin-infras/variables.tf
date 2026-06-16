variable "credentials" {
  description = "My Credentials"
  default     = "./key/bruin-bq-cred.json"
}


variable "project" {
  description = "Project"
  default     = "bruin-taxi-project"
}

variable "region" {
  description = "Region"
  default     = "northamerica-northeast2"
}

variable "location" {
  description = "Project Location"
  default     = "northamerica-northeast2"
}

variable "bq_ingestion_dataset_name" {
  description = "My BigQuery Dataset Name"
  default     = "ingestion"
}

variable "bq_staging_dataset_name" {
  description = "My BigQuery Dataset Name"
  default     = "staging"
}

variable "bq_reports_dataset_name" {
  description = "My BigQuery Dataset Name"
  default     = "reports"
}

variable "gcs_bucket_name" {
  description = "My Storage Bucket Name"
  default     = "bruin-taxi-bucket-mod5"
}

variable "gcs_storage_class" {
  description = "Bucket Storage Class"
  default     = "STANDARD"
}