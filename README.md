# URL Shortener Service

 URL shortener built with FastAPI, PostgreSQL, redis. The service supports creating short URLs, redirecting, and admin stats. Metrics are recorded asynchronously directly to the database.


# Quick start (clean)

```bash
# from repository root
cd /{projectRoot}
# stop and remove existing containers and volumes (clean DB)
docker compose down -v
# build and start the application stack
docker compose up --build

docker compose down -v && docker compose up --build tests
```

Notes
- The development `docker-compose.yml` starts three services: `web` (FastAPI), `db` (Postgres), and `redis` (used for redirect caching and rate-limiting). The application records click metrics directly to PostgreSQL (DB-only) by default.

- API is served at http://localhost:8080 .

## API documentation & sample requests

- Swagger UI: http://localhost:8080/docs
- Redoc: http://localhost:8080/redoc

### postman collection API shared as it always have the update endpoints
- postman collection: https://api.postman.com/collections/20719923-7c1c410c-2903-414a-93a3-23b30f8e12cc?access_key=PMAT-01KB7RKPEE972942FM7TDTFBS3

## Architectural overview

High level components:
- web (FastAPI): API endpoints, redirect handlers. Uses BackgroundTasks to perform non-blocking metrics updates.
- db (Postgres): Primary data store for URL mappings and click counts.
- redis:  cache for redirect target (improves redirect latency) and for rate-limiting counters.

## Design decisions and trade-offs

## 1) DB-only metrics (current)
- Decision: Each redirect schedules an asynchronous DB UPDATE to increment `click_count`.
- as per the non funtional requirements 10^5 URL's created per day.
- 1 WRP secound
- as it is read heavy application considering 100 reads per secound(as URL's increases cummulatively)
- for very high throughput scenarious we can use kafka of such. to not to make it complex and to not to loose metrics i have opted to write metrics directly to DB
### Trade-offs:
  - Pros: Simpler logic, immediate consistency in DB and admin UI, easier to reason about counts.
  - Cons: Higher write volume to the DB under heavy traffic; may need batching or a write queue for scale.

## 2) Caching
- Redis is used as a redirect cache (`url:{short_code}`) to reduce latency. If Redis is unavailable the service falls back to DB lookup.

**Trade-off when Redis is down**
    If Redis fails and  “fail close,” all redirects stop working.
    If  “fail open,” users still get redirected, just with slightly higher latency (DB lookup instead of cache hit).
    so, we're choosing fail open over fail close

## 3) Rate limiting
    - Basic IP-based rate limiting is implemented using Redis. Admin and health endpoints are exempt from rate limiting. used fixed window rate limiting for simplicity and to cocentrate more on URL shorting.


## 4) Shortening logic
DB Increment + Base62 Encoding

why && Trade off
- Collision-free:
    Each row in the DB gets a unique auto‑increment ID.
    Encoding that ID guarantees uniqueness without extra checks.
    won't increase latency on network calls for repeated collision check when we have huge number of URL's

- Short length guaranteed:
    Base62 encoding compresses numeric IDs into alphanumeric strings.
    Even billions of IDs stay under 10 characters.

- Low latency:
    No need to check for collisions in Redis/DB.
    Just encode the ID and return the short code.

- Predictable but safe:
    Yes, codes are sequential/predictable, but that’s not a security issue u\
    For most URL shorteners, predictability is acceptable