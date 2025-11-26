#!/bin/sh
# Wait until PostgreSQL is ready to accept connections

set -e
host="$1"
shift
cmd="$@"

# Using hardcoded values matching docker-compose.yml for simplicity.
until PGPASSWORD="password" psql -h "$host" -U "user" -d "shortener_db" -c '\q'; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

>&2 echo "Postgres is up - executing application command"
exec $cmd
