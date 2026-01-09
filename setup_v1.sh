#!/bin/bash

# Define colors
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}>>> Updating System...${NC}"
sudo apt update
sudo apt install python3 python3-pip python3-venv sqlite3 curl -y

# Create directory
mkdir -p /opt/my_vpn_bot
cd /opt/my_vpn_bot

echo -e "${GREEN}>>> Downloading Files...${NC}"
# التأكد من سحب الروابط بصيغة Raw الصحيحة
curl -sL "https://raw.githubusercontent.com/Affuyfuffyt/Bot-v2ray-cntroll/main/x99_core_run.py" -o main_bot.py
curl -sL "https://raw.githubusercontent.com/Affuyfuffyt/Bot-v2ray-cntroll/main/req_z55.txt" -o requirements.txt

echo -e "${GREEN}>>> Setting up Python Environment...${NC}"
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo -e "${GREEN}>>> Configuration:${NC}"
read -p "Enter Telegram Bot Token: " BOT_TOKEN
read -p "Enter Admin ID: " ADMIN_ID

sed -i "s/TOKEN_PLACEHOLDER/$BOT_TOKEN/g" main_bot.py
sed -i "s/ADMIN_ID_PLACEHOLDER/$ADMIN_ID/g" main_bot.py

cat <<EOF > /etc/systemd/system/vpn_bot_x99.service
[Unit]
Description=Telegram VPN Bot Service
After=network.target

[Service]
User=root
WorkingDirectory=/opt/my_vpn_bot
ExecStart=/opt/my_vpn_bot/venv/bin/python main_bot.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable vpn_bot_x99
systemctl start vpn_bot_x99

echo -e "${GREEN}>>> Installation Complete! The bot is running.${NC}"
