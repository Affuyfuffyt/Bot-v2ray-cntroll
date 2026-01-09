import telebot
from telebot import types
import sqlite3
import uuid
import json
import base64
import requests
import os

# --- الإعدادات الأساسية (يتم استبدالها تلقائياً عند التثبيت) ---
BOT_TOKEN = "TOKEN_PLACEHOLDER"
ADMIN_ID = "ADMIN_ID_PLACEHOLDER"

bot = telebot.TeleBot(BOT_TOKEN)
DB_NAME = "srv_data_z77.db"

# جلب IP السيرفر تلقائياً
def get_server_ip():
    try:
        return requests.get('https://api.ipify.org').text
    except:
        return "127.0.0.1"

SERVER_IP = get_server_ip()

# --- قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, protocol TEXT, port TEXT, path TEXT,
        uuid_str TEXT, host TEXT, quota TEXT, users_limit TEXT, duration TEXT,
        channel TEXT, description TEXT, interaction_target INTEGER DEFAULT 0,
        interaction_current INTEGER DEFAULT 0, status TEXT DEFAULT 'active' 
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS interactions (
        task_id INTEGER, user_id INTEGER, UNIQUE(task_id, user_id)
    )''')
    conn.commit()
    conn.close()

init_db()
user_steps = {}

# --- دوال توليد الكودات ---
def generate_config(p_type, u_id, host, port, path, name):
    is_tls = "tls" if str(port) == "443" else "none"
    
    if p_type == "vmess":
        conf = {
            "v": "2", "ps": name, "add": host, "port": port, "id": u_id,
            "aid": "0", "scy": "auto", "net": "ws", "type": "none", "host": host,
            "path": path, "tls": is_tls, "sni": host if is_tls == "tls" else ""
        }
        return "vmess://" + base64.b64encode(json.dumps(conf).encode('utf-8')).decode('utf-8')
    
    elif p_type == "vless":
        tls_part = f"&security={is_tls}" + (f"&sni={host}" if is_tls == "tls" else "")
        return f"vless://{u_id}@{host}:{port}?encryption=none&type=ws&host={host}&path={path}{tls_part}#{name}"
    
    elif p_type == "trojan":
        tls_part = f"&security={is_tls}" + (f"&sni={host}" if is_tls == "tls" else "")
        return f"trojan://{u_id}@{host}:{port}?type=ws&host={host}&path={path}{tls_part}#{name}"

# --- واجهة البوت ---
@bot.message_handler(commands=['start'])
def welcome(message):
    if str(message.from_user.id) != str(ADMIN_ID): return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🚀 إنشاء كود جديد", "📂 الكودات المنشورة")
    bot.send_message(message.chat.id, "أهلاً بك في لوحة تحكم السيرفر العربي 🛠", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🚀 إنشاء كود جديد")
def start_creation(message):
    user_steps[message.from_user.id] = {}
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("VMess", callback_data="p_vmess"),
               types.InlineKeyboardButton("VLESS", callback_data="p_vless"),
               types.InlineKeyboardButton("Trojan", callback_data="p_trojan"))
    bot.send_message(message.chat.id, "1️⃣ اختر نوع البروتوكول:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("p_"))
def set_proto(call):
    user_steps[call.from_user.id]['protocol'] = call.data.split("_")[1]
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("80 (بدون TLS)", callback_data="port_80"),
               types.InlineKeyboardButton("443 (مع TLS)", callback_data="port_443"))
    bot.edit_message_text("2️⃣ اختر المنفذ (Port):", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("port_"))
def set_port(call):
    user_steps[call.from_user.id]['port'] = call.data.split("_")[1]
    # هنا تم إضافة خيار الـ IP التلقائي واليدوي
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(f"استخدام IP السيرفر ({SERVER_IP})", callback_data="ip_auto"),
               types.InlineKeyboardButton("إدخال IP/دومين يدوي", callback_data="ip_manual"))
    bot.edit_message_text("3️⃣ اختر عنوان الاتصال (Host):", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("ip_"))
def set_ip_choice(call):
    if call.data == "ip_auto":
        user_steps[call.from_user.id]['host'] = SERVER_IP
        ask_path(call.message)
    else:
        msg = bot.send_message(call.message.chat.id, "أرسل الـ IP أو الدومين الآن:")
        bot.register_next_step_handler(msg, save_manual_ip)

def save_manual_ip(message):
    user_steps[message.from_user.id]['host'] = message.text
    ask_path(message)

def ask_path(message):
    msg = bot.send_message(message.chat.id, "4️⃣ أدخل المسار (Path) - مثال: /v2ray")
    bot.register_next_step_handler(msg, save_path)

def save_path(message):
    user_steps[message.from_user.id]['path'] = message.text
    user_steps[message.from_user.id]['uuid'] = str(uuid.uuid4())
    msg = bot.send_message(message.chat.id, "5️⃣ أدخل وصف الكود (مثلاً: سيرفر مجاني سريع):")
    bot.register_next_step_handler(msg, save_desc)

def save_desc(message):
    user_steps[message.from_user.id]['description'] = message.text
    msg = bot.send_message(message.chat.id, "6️⃣ أدخل يوزر القناة مع @ (مثال: @MyChannel):")
    bot.register_next_step_handler(msg, finalize)

def finalize(message):
    user_steps[message.from_user.id]['channel'] = message.text
    data = user_steps[message.from_user.id]
    
    # تفاصيل افتراضية للنشر
    data['quota'] = "غير محدود"
    data['users_limit'] = "مفتوح"
    data['duration'] = "30 يوم"
    
    code = generate_config(data['protocol'], data['uuid'], data['host'], data['port'], data['path'], "V2RAY_FREE")
    
    publish_text = (
        f"🚀 **كود اتصال جديد ({data['protocol'].upper()})**\n"
        f"━━━━━━━━━━━━━━\n"
        f"📝 **الوصف:** {data['description']}\n"
        f"📡 **النوع:** {data['protocol']}\n"
        f"🔌 **المنفذ:** {data['port']}\n"
        f"💾 **الحجم:** {data['quota']}\n"
        f"⏳ **الصلاحية:** {data['duration']}\n"
        f"━━━━━━━━━━━━━━\n"
        f"🔗 **انسخ الكود من هنا:**\n`{code}`"
    )
    
    try:
        bot.send_message(data['channel'], publish_text, parse_mode="Markdown")
        bot.send_message(message.chat.id, "✅ تم النشر بنجاح في القناة!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ فشل النشر. تأكد أن البوت مشرف في القناة.\nالخطأ: {e}")

bot.infinity_polling()
