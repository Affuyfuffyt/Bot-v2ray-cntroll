Enter#!/bin/bash

# Define colors
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}>>> Updating System...${NC}"
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv sqlite3 -y

# Create directory
mkdir -p /opt/my_vpn_bot
cd /opt/my_vpn_bot

echo -e "${GREEN}>>> Downloading Files...${NC}"
# ملاحظة: سيقوم المستخدم باستبدال الرابط هنا برابط مستودعه
curl -sL https://raw.githubusercontent.com/USER_NAME/REPO_NAME/main/x99_core_run.py -o main_bot.py
curl -sL https://raw.githubusercontent.com/USER_NAME/REPO_NAME/main/req_z55.txt -o requirements.txt

echo -e "${GREEN}>>> Setting up Python Environment...${NC}"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Ask for configuration
echo -e "${GREEN}>>> Configuration:${NC}"
read -p "Enter Telegram Bot Token: " BOT_TOKEN
read -p "Enter Admin ID: " ADMIN_ID

# Replace placeholders in the python file
sed -i "s/TOKEN_PLACEHOLDER/$BOT_TOKEN/g" main_bot.py
sed -i "s/ADMIN_ID_PLACEHOLDER/$ADMIN_ID/g" main_bot.py

echo -e "${GREEN}>>> Creating Systemd Service...${NC}"
cat <<EOF > /etc/systemd/system/vpn_bot_x99.service
[Unit]
Description=Telegram VPN Bot Service
After=network.target

[Service]
User=root
WorkingDirectory=/opt/my_vpn_bot
ExecStart=/opt/my_vpn_bot/venv/bin/python main_bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Enable and Start
systemctl daemon-reload
systemctl enable vpn_bot_x99
systemctl start vpn_bot_x99

echo -e "${GREEN}>>> Installation Complete! The bot is running.${NC}"
