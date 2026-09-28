#!/bin/bash
# KEPLER — Oracle Cloud VM startup script
# Run this once after SSH-ing into a fresh Ubuntu 22.04 VM

set -e

echo "=== KEPLER Backend Setup ==="

# 1. System deps
sudo apt-get update -y
sudo apt-get install -y python3-pip python3-venv git screen ufw

# 2. Allow port 8000 through firewall
sudo ufw allow 8000
sudo ufw allow 22
sudo ufw --force enable

# 3. Clone repo (replace with your actual repo URL)
# git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git /home/ubuntu/kepler
# cd /home/ubuntu/kepler/backend

# 4. If already cloned, just pull latest
# git pull origin main

# 5. Set up Python venv
cd backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 6. Set up .env
if [ ! -f .env ]; then
  cp .env.example .env
  echo ">>> IMPORTANT: Edit .env with your real values before continuing <<<"
  echo ">>> Run: nano .env"
  exit 1
fi

# 7. Run DB migration
python migrate.py

echo "=== Setup complete. Starting server... ==="
