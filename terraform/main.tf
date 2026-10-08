terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Deploy the FastAPI & Scraper container to Cloud Run
resource "google_cloud_run_v2_service" "power_alerts_api" {
  name     = "bih-power-alerts"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = var.docker_image
      
      ports {
        container_port = 8000
      }

      env {
        name  = "DATABASE_URL"
        value = var.database_url
      }
      
      # Ensure Prometheus metrics and JSON logs are output correctly
      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }
    }
    
    # Scale to zero when not in use to maintain 100% free tier
    scaling {
      max_instance_count = 1
      min_instance_count = 0
    }
  }
}

# Make the Cloud Run URL public so the PWA Frontend is accessible
resource "google_cloud_run_service_iam_member" "public_access" {
  location = google_cloud_run_v2_service.power_alerts_api.location
  project  = google_cloud_run_v2_service.power_alerts_api.project
  service  = google_cloud_run_v2_service.power_alerts_api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
