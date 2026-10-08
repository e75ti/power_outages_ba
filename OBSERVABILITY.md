# Observability & Telemetry

A scraper is inherently fragile. Utility companies change their website layouts without warning, drop connections, or change their date formats. 

To ensure this service remains highly available, I integrated a full Site Reliability Engineering (SRE) observability stack into the Docker Compose network. The goal is to detect a scraper failure and alert me before a user misses a power outage notification.

## The Stack

1. **Prometheus (Metrics Collection):**
   - Scrapes the FastAPI `/metrics` endpoint every 15 seconds.
   - Tracks custom metrics: `outages_collected_total`, `scraper_duration_seconds`, and `active_database_connections`.

2. **Grafana Loki & Alloy (Log Aggregation):**
   - Instead of manually SSHing into the server to run `docker logs`, I implemented structured JSON logging (`python-json-logger`) across the Python backend.
   - Grafana Alloy binds to the Docker socket, intercepts all container `stdout`/`stderr` streams, and forwards them to Loki.
   - This allows me to query logs using LogQL directly inside Grafana (e.g., `{container="outage-scraper"} |= "error"`).

3. **Grafana (Visualization):**
   - Serves as the single pane of glass for the system.
   - The primary dashboard visualizes latency per utility provider, historical outage volumes, and API request error rates.

## Alerting Strategy

The system is configured to push alerts to a private Telegram Admin channel under these conditions:
- **Scraper Failure:** If `outages_collected_total` drops by more than 80% compared to the 24-hour baseline.
- **API Latency:** If the FastAPI p95 response time exceeds 2 seconds.
- **Container Restarts:** If any Docker container restarts more than 3 times in 10 minutes (indicating an Out-of-Memory error or crash loop).
