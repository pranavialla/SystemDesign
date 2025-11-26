# Stage 1: Builder
FROM python:3.11-alpine as builder
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
# Install build dependencies for psycopg2
RUN apk add --no-cache postgresql-dev gcc python3-dev musl-dev
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --prefix=/install -r requirements.txt

# Stage 2: Final lightweight image
FROM python:3.11-alpine
WORKDIR /app
# Install runtime dependencies
RUN apk add --no-cache libpq
# Install PostgreSQL client tools (required for healthcheck.sh)
RUN apk add --no-cache postgresql-client 

# Copy installed packages from the builder stage
COPY --from=builder /install /usr/local
# Copy application code and health check script
COPY . .
# Create and switch to a non-root user for security
RUN adduser -D appuser
USER appuser
# Expose the service on port 8080
EXPOSE 8080
# NOTE: CMD is set by docker-compose to run the healthcheck wrapper first
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
