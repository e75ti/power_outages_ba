output "application_url" {
  description = "The live public URL of your Cloud Run application"
  value       = google_cloud_run_v2_service.power_alerts_api.uri
}
