# URL Shortener Service

A small production-ready URL shortener built with FastAPI, SQLAlchemy and PostgreSQL. The service supports creating short URLs, redirecting, and admin stats. Metrics are recorded asynchronously directly to the database.

## Setup & run instructions

Prerequisites
- Docker Desktop (or Docker Engine + Docker Compose v2)
- Git

Quick start (clean)

```bash
# from repository root
cd /path/to/SystemDesign/URLShortner
# stop and remove existing containers and volumes (clean DB)
docker compose down -v
# build and start the application stack
docker compose up --build
```

Notes
- The development `docker-compose.yml` starts three services: `web` (FastAPI), `db` (Postgres), and `redis` (used for redirect caching and rate-limiting). The application records click metrics directly to PostgreSQL (DB-only) by default.
- API is served at http://localhost:8080 by the compose stack.

## API documentation & sample requests

Open interactive docs in your browser after starting the stack:

- Swagger UI: http://localhost:8080/docs
- Redoc: http://localhost:8080/redoc

1) Create a short URL

Request

```bash
curl -s -X POST http://localhost:8080/api/v1/shorten \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/long/path"}' | jq .
```

Response (example)

```json
{
  "original_url": "https://example.com/long/path",
  "short_code": "abc12345",
  "short_url": "http://localhost:8080/abc12345",
  "created_at": "2025-11-27T19:18:40.953574",
  "last_accessed_at": null,
  "click_count": 0
}
```

2) Redirect via short code (browser or CLI)

```bash
# follow the redirect and show the final status code
curl -L -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/abc12345
```

3) Admin: URL stats

```bash
curl -s http://localhost:8080/api/v1/admin/stats/abc12345 | jq .
```

Response (example)

```json
{
  "url": "https://example.com/long/path",
  "short_code": "abc12345",
  "short_url": "http://localhost:8080/abc12345",
  "created_at": "2025-11-27T19:18:40.953574",
  "last_accessed_at": "2025-11-27T19:22:25.865711",
  "click_count": 3
}
```

## Architectural overview

High level components:
- web (FastAPI): API endpoints, redirect handlers. Uses BackgroundTasks to perform non-blocking metrics updates.
- db (Postgres): Primary data store for URL mappings and click counts.
- redis: Optional cache for redirect target (improves redirect latency) and for rate-limiting counters.

Flow for a redirect
1. Request arrives at GET /{short_code}
2. Check Redis cache for `url:{short_code}`
   - If present: return RedirectResponse immediately and schedule background DB update.
   - If missing: look up DB, set Redis cache, schedule DB update, return redirect.
3. Background job runs `metrics.record_click(short_code)` which performs a single SQL UPDATE to increment `click_count` and update `last_accessed_at`.

(Optionally, for very high throughput, a Redis INCR + periodic batch flush to DB is recommended to reduce write amplification.)

## Design decisions and trade-offs

1) DB-only metrics (current)
- Decision: Each redirect schedules an asynchronous DB UPDATE to increment `click_count`.
- Trade-offs:
  - Pros: Simpler logic, immediate consistency in DB and admin UI, easier to reason about counts.
  - Cons: Higher write volume to the DB under heavy traffic; may need batching or a write queue for scale.

2) Caching
- Redis is used as a redirect cache (`url:{short_code}`) to reduce latency. If Redis is unavailable the service falls back to DB lookup.

3) Rate limiting
- Basic IP-based rate limiting is implemented using Redis. Admin and health endpoints are exempt from rate limiting.

4) Idempotency
- Short codes generated deterministically (SHA256-based) from the original URL to make repeated shorten requests idempotent.

5) Migrations
- Current setup uses SQLAlchemy `create_all` on startup for simplicity. For production use, integrate Alembic for proper migrations.

