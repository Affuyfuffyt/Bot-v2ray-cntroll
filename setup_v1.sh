#!/bin/bash
# تحديث رقم 2 - تنظيف كامل وإعادة تثبيت

GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}>>> [1/5] Cleaning old files...${NC}"
systemctl stop vpn_bot_x99 2>/dev/null
rm -rf /opt/my_vpn_bot
rm -f /etc/systemd/system/vpn_bot_x99.service

echo -e "${GREEN}>>> [2/5] Installing dependencies...${NC}"
apt update && apt install python3 python3-pip python3-venv sqlite3 curl -y

echo -e "${GREEN}>>> [3/5] Setting up environment...${NC}"
mkdir -p /opt/my_vpn_bot
cd /opt/my_vpn_bot
python3 -m venv venv

echo -e "${GREEN}>>> [4/5] Downloading latest code...${NC}"
curl -sL "https://raw.githubusercontent.com/Affuyfuffyt/Bot-v2ray-cntroll/main/x99_core_run.py" -o main_bot.py
curl -sL "https://raw.githubusercontent.com/Affuyfuffyt/Bot-v2ray-cntroll/main/req_z55.txt" -o requirements.txt

./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo -e "${GREEN}>>> [5/5] Configuration:${NC}"
read -p "Enter Telegram Bot Token: " BOT_TOKEN
read -p "Enter Admin ID: " ADMIN_ID

sed -i "s/TOKEN_PLACEHOLDER/$BOT_TOKEN/g" main_bot.py
sed -i "s/ADMIN_ID_PLACEHOLDER/$ADMIN_ID/g" main_bot.py

# Create System Service
cat <<EOF > /etc/systemd/system/vpn_bot_x99.service
[Unit]
Description=Telegram VPN Bot V2
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

echo -e "${GREEN}>>> Done! Everything is updated and running.${NC}"
