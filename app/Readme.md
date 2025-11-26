# 1. Make the setup script executable (if not already)
chmod +x setup.sh

# 2. Run the script to generate all files (ensures all fixes are applied)
./setup.sh

# 3. Shut down and remove old containers/volumes for a clean start
# This ensures that cached/old database data and images are removed.
docker compose down -v 

# 4. Build the new Docker image and start the application stack
docker compose up --build