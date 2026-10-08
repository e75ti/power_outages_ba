variable "project_id" {
  description = "The GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region (e.g., europe-west3 for Frankfurt)"
  type        = string
  default     = "europe-west3"
}

variable "docker_image" {
  description = "The URL of the Docker image in Google Artifact Registry"
  type        = string
}

variable "database_url" {
  description = "Connection string for Serverless Postgres (e.g., Neon.tech)"
  type        = string
  sensitive   = true
}
