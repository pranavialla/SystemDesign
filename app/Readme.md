# 1. Shut down and remove old containers/volumes for a clean start
# This ensures that cached/old database data and images are removed.
docker compose down -v 

# 2. Build the new Docker image and start the application stack
docker compose up --build