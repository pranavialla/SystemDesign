# URL Shortener Service


## 📖 Index (Table of Contents)

- [ Functional Requirements](#1-functional-requirements)

- [ Non-Functional Requirements](#2-non-functional-requirements)

- [ Data Modeling](#3-data-modeling)

- [ Back-of-Envelope Estimations](#4-back-of-envelope-estimations)

- [ API Design](#5-api-design)

- [ Design Decisions & Trade-offs](#6-design-decisions--trade-offs)
  
- [ Repository & CI/CD](#repository--cicd)
 
- [ Quick Setup](#quick-setup)


## 1. Functional Requirements

### Core Capabilities
- **URL Shortening**: Accept long URLs and return unique short URL (max 10 characters shortcode)
- **URL Redirection**: Redirect users from short URLs to original destinations
- **Idempotency**: Same original URL always returns the same short URL
- **Custom Aliases**: Support user-defined short codes
- **Analytics**: Track click counts and last access timestamps
- **Admin Operations**: 
  - List all URLs with pagination
  - Retrieve detailed statistics per short code

### Input Validation
- URL length limit: 2048 characters
- Custom alias length: max 10 characters
- Collision detection and graceful handling


## 2. Non-Functional Requirements
### Performance
- **Latency**: Redirects must complete in <100ms
- **Throughput**: Handle 10,000 new URL creations per day (~0.12 writes/sec)
- **Read-Heavy**: Optimized for 100+ redirects/sec with caching

### Scalability
- **Data Retention**: Store URLs for minimum 5 years
- **Volume**: Support billions of URLs over time
- **Growth**: 10K URLs/day → ~18M URLs in 5 years

### Rate limiting
- **Rate limiting**: Request limits per IP address

---

## 3. Data Modeling

### PostgreSQL Schema

#### URLs Table
```
  urls 
    id SERIAL PRIMARY KEY              
    ID for Base62 encoding
    short_code VARCHAR(10)  (INDEX)
    original_url TEXT 
    created_at TIMESTAMP 
    last_accessed_at TIMESTAMP 
    click_count INTEGER 
```

#### System Configuration Table
```sql
  system_configs
    key 
    value 

```

### Redis Cache Structure

```
Redirect Cache (24-hour TTL)
url:{short_code} → original_url

Rate Limiting (60-second sliding window)
rate_limit:{client_ip} → request_count

config:RATE_LIMIT_LIMIT → "100"
config:RATE_LIMIT_WINDOW → "60"
```

---

## 4. Back-of-Envelope Estimations

### Traffic Calculations
```
Writes: 10,000 URLs/day ≈ 0.12 writes/sec (peak: ~1 write/sec)
Reads: 100 redirects/sec
Read:Write Ratio = 100:1 (highly read-heavy)
```

### Storage Requirements
```
Per URL record:
- short_code: 10 bytes
- original_url: ~200 bytes avg
- metadata: ~50 bytes (timestamps, counts)
Total: ~260 bytes/URL

5-Year Storage:
10K URLs/day × 365 days × 5 years = 18.25M URLs
18.25M × 260 bytes ≈ 4.75 GB
```

### Short Code Capacity
```
Base36 encoding: [0-9a-z] = 36 characters
10 characters: 36^10 ≈ 3.66 quadrillion unique codes

With 18M URLs in 5 years, 10-character codes provide ~203,000,000× capacity buffer
```


---

## 5. API Design


### API Documentation
- **Postman Collection**: [View & Test APIs](https://api.postman.com/collections/20719923-7c1c410c-2903-414a-93a3-23b30f8e12cc?access_key=PMAT-01KB7RKPEE972942FM7TDTFBS3)
- **Swagger UI**: `http://localhost:8080/docs`
- **ReDoc**: `http://localhost:8080/redoc`

---

## 6. Design Decisions & Trade-offs

### Decision 1: Base32 Encoding from secret pacakage

**Alternative Approaches**: 

1. Use PostgreSQL auto-increment ID → Base62 encode → short_code

    #### pro
    - **Simple Logic**: Single DB insert, encode, update short_code

    #### con's
    - Predictable (users can scrape data by guessing codes).
    - Requires centralized coordination when we have multiple instances.
    - it don't help us to avoid collision too as we support custom alias. if custom alias is not supported then this approch is collision free

2. Base62 Encoding from secret pacakage
    #### pro
    -  The code is cryptographically unpredictable, making it difficult for malicious users to enumerate or guess other active URLs by simply incrementing a character.
    - large shortcode space. so very less chance for collision

    #### con's
    -  confusion due to case sensitiveness. user not only need to remeber shortcode they need to remeber each character case
    

#### implemented approch

3. Base32 Encoding from secret pacakage
    #### pro's
    - eliminates confusion when a user reads, writes, or shares the short code verbally 
    - provides a massive address space ($3.65 \times 10^{15}$ combinations). Since the service only stores $\approx 1.8 \times 10^7$ URLs, the probability of hitting a collision is extremely low, making the "check-and-retry" logic very efficient
    - The code is cryptographically unpredictable, making it difficult for malicious users to enumerate or guess other active URLs by simply incrementing a character.

    #### cons's
    - Requires database lookup to ensure the short code hasn't been used before.
    - Required database lookup for Idempotency check




### Decision 2: Write-Through Cache with Fail-Open

**Approach**: Cache redirects in Redis; fall back to DB if cache misses or Redis is down

**Cache Strategy**:
```python
1. Check Redis for url:{short_code}
   ├─ HIT → Return immediately
   └─ MISS → Query PostgreSQL
       └─ Cache result in Redis
```

**Why Fail-Open**:
- Service continues during Redis outages
- Slight latency increase (10-15ms) is acceptable vs. downtime

### Decision 3: 302 (Found / Temporary Redirect) Redirection status code

1. 301 (Moved Permanently)

    #### Pros
    - Search engines transfer link ranking to the destination.
    - Caching: Browsers and proxies cache aggressively, reducing repeated redirect lookups.
    - Fewer repeated requests on our server since clients assume the mapping is permanent.

    #### con's
    -Inflexibility: Once cached, changing the destination is difficult; users may be stuck with stale redirects.
    - Not suitable for dynamic or campaign links where the target may change.
    - Risk of misconfiguration: If you later need to change the destination, cached 301s can cause broken links.

#### implemented approch
    
2. 302 (Found / Temporary Redirect)
    #### Pros:
    - Flexibility: Indicates the destination may change, ideal for shorteners where links can be updated.
    - SEO-safe: Search engines generally keep the shortener indexed and don’t transfer full ranking signals, preventing SEO hijacking.
    - our srver can maintain URL analytics.

    #### Cons:
    - Performance: Redirects are not cached as aggressively, so each request may hit the shortener service.
    - SEO trade-off: Less link equity passed to the destination compared to 301.
    - Slightly higher latency due to repeated lookups.

---

## Repository & CI/CD

- **GitHub**: [SystemDesign Repository](https://github.com/pranavialla/SystemDesign)
- **CI/CD Pipeline**: [GitHub Actions Workflows](https://github.com/pranavialla/SystemDesign/actions)
- **Docker Hub**: `apranavi/url-shortener:latest`

### Deployment Flow
```
1. Developer pushes to main branch
2. GitHub Actions triggers:
   ├─ Run pytest suite (unit + integration tests)
   ├─ Build Docker image (multi-stage Alpine)
   ├─ Push to Docker Hub 
   └─ Trigger Render deployment webhook
```

# Quick setup
### Running the URL Shortener Service using docker image

1. **Pull the image**
   ```bash
   docker pull apranavi/url-shortener:latest

2. **run**
    ```bash 
    docker run -d --name url-shortener -p 8000:8000 apranavi/url-shortener:latest

2. **Stop the service**
    ```bash 
    docker stop url-shortener 

3. **remove**
    ```bash 
    docker rm url-shortener



### Steps to run if Source code pulled from GIT

    from repository root
    cd /{projectRoot}
    
    stop and remove existing containers and volumes (clean DB)
    docker compose down -v

    to remove container but without volumes clean
    docker compose down

    build and start the application stack
    docker compose up --build

    docker compose down -v && docker compose up --build tests


---
