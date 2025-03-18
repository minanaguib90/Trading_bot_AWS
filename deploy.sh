#!/bin/bash

# Create necessary directories
mkdir -p logs

# Install Python and required packages
sudo apt update
sudo apt install -y python3-pip python3-venv

# Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# Install or upgrade pip
python3 -m pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

# Create systemd service file
sudo tee /etc/systemd/system/trading-bot.service << EOF
[Unit]
Description=Trading Bot Service
After=network.target

[Service]
User=$USER
WorkingDirectory=$(pwd)
Environment="PATH=$(pwd)/venv/bin"
ExecStart=$(pwd)/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable trading-bot
sudo systemctl start trading-bot

echo "Deployment completed. Check status with: sudo systemctl status trading-bot"
