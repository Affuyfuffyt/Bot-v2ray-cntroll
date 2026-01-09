#!/bin/bash
# تصفية كاملة وإعادة تثبيت

GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}>>> [1/3] تنظيف السيرفر كلياً...${NC}"
systemctl stop vpn_bot_x99 2>/dev/null
rm -rf /opt/my_vpn_bot
rm -f /etc/systemd/system/vpn_bot_x99.service

echo -e "${GREEN}>>> [2/3] تحديث الأدوات...${NC}"
apt update && apt install python3 python3-pip python3-venv sqlite3 curl -y

echo -e "${GREEN}>>> [3/3] تحميل الكود الجديد والتشغيل...${NC}"
mkdir -p /opt/my_vpn_bot
cd /opt/my_vpn_bot

curl -sL "https://raw.githubusercontent.com/Affuyfuffyt/Bot-v2ray-cntroll/main/x99_core_run.py" -o main_bot.py
curl -sL "https://raw.githubusercontent.com/Affuyfuffyt/Bot-v2ray-cntroll/main/req_z55.txt" -o requirements.txt

python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install pyTelegramBotAPI requests schedule

echo -e "${GREEN}>>> Configuration:${NC}"
read -p "Enter Telegram Bot Token: " BOT_TOKEN
read -p "Enter Admin ID: " ADMIN_ID

sed -i "s/TOKEN_PLACEHOLDER/$BOT_TOKEN/g" main_bot.py
sed -i "s/ADMIN_ID_PLACEHOLDER/$ADMIN_ID/g" main_bot.py

cat <<EOF > /etc/systemd/system/vpn_bot_x99.service
[Unit]
Description=VPN Bot V2.5
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

echo -e "${GREEN}>>> مبروك! البوت يعمل الآن بنظام الأكواد المصلح.${NC}"
