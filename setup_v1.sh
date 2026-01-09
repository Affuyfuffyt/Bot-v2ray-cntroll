#!/bin/bash
# نظام التثبيت الاحترافي - حذف وإعادة تثبيت شاملة

GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}>>> [1/4] تنظيف السيرفر من المخلفات القديمة...${NC}"
systemctl stop vpn_bot_x99 2>/dev/null
systemctl disable vpn_bot_x99 2>/dev/null
rm -rf /opt/my_vpn_bot
rm -f /etc/systemd/system/vpn_bot_x99.service
rm -f /usr/bin/sqlite3

echo -e "${GREEN}>>> [2/4] تثبيت الأدوات والاعتمادات...${NC}"
apt update && apt upgrade -y
apt install python3 python3-pip python3-venv sqlite3 curl -y

echo -e "${GREEN}>>> [3/4] إنشاء البيئة وتحميل الملفات...${NC}"
mkdir -p /opt/my_vpn_bot
cd /opt/my_vpn_bot

# حذف أي نسخ محملة مسبقاً قبل التحميل الجديد
rm -f main_bot.py requirements.txt

curl -sL "https://raw.githubusercontent.com/Affuyfuffyt/Bot-v2ray-cntroll/main/x99_core_run.py" -o main_bot.py
curl -sL "https://raw.githubusercontent.com/Affuyfuffyt/Bot-v2ray-cntroll/main/req_z55.txt" -o requirements.txt

python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

echo -e "${GREEN}>>> [4/4] إعداد بيانات البوت...${NC}"
read -p "Enter Telegram Bot Token: " BOT_TOKEN
read -p "Enter Admin ID: " ADMIN_ID

sed -i "s/TOKEN_PLACEHOLDER/$BOT_TOKEN/g" main_bot.py
sed -i "s/ADMIN_ID_PLACEHOLDER/$ADMIN_ID/g" main_bot.py

# إنشاء الخدمة لضمان استمرار العمل
cat <<EOF > /etc/systemd/system/vpn_bot_x99.service
[Unit]
Description=Telegram VPN Bot Full Version
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

systemctl daemon-reload
systemctl enable vpn_bot_x99
systemctl start vpn_bot_x99

echo -e "${GREEN}>>> تم التثبيت بنجاح! البوت يعمل الآن بكامل طاقته.${NC}"
