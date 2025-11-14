#!/usr/bin/env bash
set -euo pipefail

# deploy/start-prod.sh
# Usage: run this on the VM as your non-root deploy user. The script will:
# - install Docker & docker compose plugin (Ubuntu/Debian)
# - clone the repo to /opt/luro (if not present) or pull latest
# - prompt you to edit .env (creates from .env.example if missing)
# - build and start containers
# - run alembic migrations
# - optionally install nginx + certbot (uncomment the CERTBOT block)

REPO_URL="https://github.com/alexarnoni/Luro.git"
REPO_DIR="/opt/luro"

echo "Starting Luro deploy helper"

if [ "$(id -u)" -eq 0 ]; then
  echo "It is recommended to run this script as a regular user with sudo privileges, not as root." >&2
fi

install_docker() {
  if command -v docker >/dev/null 2>&1; then
    echo "Docker already installed"
    return
  fi
  echo "Installing Docker & docker compose plugin (requires sudo)..."
  sudo apt update
  sudo apt install -y ca-certificates curl gnupg lsb-release
  sudo mkdir -p /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt update
  sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  echo "Docker installed. Adding current user to docker group (you may need to re-login)"
  sudo usermod -aG docker $(whoami) || true
}

clone_or_pull() {
  if [ ! -d "$REPO_DIR/.git" ]; then
    echo "Cloning repository into $REPO_DIR"
    sudo mkdir -p "$REPO_DIR"
    sudo chown -R $(whoami):$(whoami) "$REPO_DIR"
    git clone "$REPO_URL" "$REPO_DIR"
  else
    echo "Repository already present, pulling latest"
    cd "$REPO_DIR"
    git pull --ff-only || true
  fi
}

ensure_env() {
  cd "$REPO_DIR"
  if [ ! -f .env ]; then
    echo "Creating .env from .env.example (you must edit it and set SECRET_KEY, POSTGRES_PASSWORD, etc.)"
    cp .env.example .env
    echo "Please edit $REPO_DIR/.env now (it will open nano). After saving and exiting, the script will continue."
    nano .env
  else
    echo ".env already exists in $REPO_DIR (will not be overwritten)."
    echo "If you need to change secrets, edit .env now."
    read -p "Press ENTER to continue (or Ctrl-C to abort)"
  fi
}

start_compose() {
  cd "$REPO_DIR"
  echo "Building and starting containers (this may take a few minutes)..."
  docker compose -f docker-compose.prod.yml up -d --build
}

run_migrations() {
  cd "$REPO_DIR"
  echo "Running alembic migrations inside the web service"
  docker compose -f docker-compose.prod.yml run --rm web alembic upgrade head
}

install_nginx_and_certbot() {
  echo "Installing nginx and certbot (requires sudo)..."
  sudo apt update
  sudo apt install -y nginx
  sudo cp deploy/luro.nginx.conf /etc/nginx/sites-available/luro.conf
  sudo ln -sf /etc/nginx/sites-available/luro.conf /etc/nginx/sites-enabled/luro.conf
  sudo nginx -t
  sudo systemctl reload nginx
  echo "If you provided a DOMAIN and DNS is pointed, run certbot to obtain TLS certs:"
  echo "  sudo apt install -y certbot python3-certbot-nginx"
  echo "  sudo certbot --nginx -d YOUR_DOMAIN_HERE"
}

main() {
  install_docker
  clone_or_pull
  ensure_env
  start_compose
  echo "Waiting 3 seconds for services to spin up..."
  sleep 3
  run_migrations
  echo "Deployment complete. Check status with: docker compose -f docker-compose.prod.yml ps"
  echo "Check web logs with: docker compose -f docker-compose.prod.yml logs -f web"
  echo "To install nginx and obtain TLS certificates, run: install_nginx_and_certbot (or follow deploy/README_DEPLOY.md)"
}

main "$@"
