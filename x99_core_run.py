import telebot
from telebot import types
import sqlite3
import uuid
import json
import base64
import requests
import time
import threading
import schedule
import os

# --- الإعدادات الأساسية ---
BOT_TOKEN = "TOKEN_PLACEHOLDER"
ADMIN_ID = "ADMIN_ID_PLACEHOLDER"

bot = telebot.TeleBot(BOT_TOKEN)
DB_NAME = "srv_data_z77.db"

def get_server_ip():
    try:
        return requests.get('https://api.ipify.org', timeout=5).text
    except:
        return "127.0.0.1"

SERVER_IP = get_server_ip()

# --- إدارة قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        protocol TEXT, port TEXT, path TEXT, uuid_str TEXT,
        host TEXT, quota TEXT, users_limit TEXT, duration TEXT,
        channel TEXT, description TEXT, interaction_target INTEGER DEFAULT 0,
        interaction_current INTEGER DEFAULT 0, interaction_msg_id INTEGER DEFAULT 0,
        interaction_chat_id INTEGER DEFAULT 0, status TEXT DEFAULT 'active' 
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS interactions (
        task_id INTEGER, user_id INTEGER, UNIQUE(task_id, user_id)
    )''')
    conn.commit()
    conn.close()

init_db()
user_creation_steps = {}

# --- دالة توليد الأكواد الاحترافية (تم الإصلاح الشامل) ---
def generate_v2ray_config(p_type, u_id, host, port, path, name):
    # التأكد من المسار يبدأ بـ /
    if not path.startswith('/'):
        path = '/' + path
        
    security = "tls" if str(port) == "443" else "none"
    
    if p_type == "vmess":
        # VMess Header
        vmess_obj = {
            "v": "2",
            "ps": name,
            "add": host,
            "port": int(port),
            "id": u_id,
            "aid": "0",
            "scy": "auto",
            "net": "ws",
            "type": "none",
            "host": host,
            "path": path,
            "tls": security,
            "sni": host if security == "tls" else "",
            "alpn": ""
        }
        json_str = json.dumps(vmess_obj)
        return "vmess://" + base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
    
    elif p_type == "vless":
        # VLESS Uri
        vless_link = f"vless://{u_id}@{host}:{port}?encryption=none&security={security}&type=ws&host={host}&path={path}"
        if security == "tls":
            vless_link += f"&sni={host}"
        vless_link += f"#{name}"
        return vless_link
    
    elif p_type == "trojan":
        # Trojan Uri
        trojan_link = f"trojan://{u_id}@{host}:{port}?security={security}&type=ws&host={host}&path={path}"
        if security == "tls":
            trojan_link += f"&sni={host}"
        trojan_link += f"#{name}"
        return trojan_link

# --- القوائم الرئيسية ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    if str(message.from_user.id) != str(ADMIN_ID): return
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add("🚀 إنشاء كود جديد", "📂 إدارة الكودات", "📊 إحصائيات", "⚙️ إعدادات")
    bot.send_message(message.chat.id, "🛠 **لوحة التحكم المتقدمة V2.5**\n\nتم إصلاح نظام الأكواد ليعمل مع جميع التطبيقات.", reply_markup=markup, parse_mode="Markdown")

# --- مراحل إنشاء الكود ---
@bot.message_handler(func=lambda message: message.text == "🚀 إنشاء كود جديد")
def start_p(message):
    user_creation_steps[message.from_user.id] = {}
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("VMess", callback_data="set_vmess"),
          types.InlineKeyboardButton("VLESS", callback_data="set_vless"),
          types.InlineKeyboardButton("Trojan", callback_data="set_trojan"))
    bot.send_message(message.chat.id, "1️⃣ اختر البروتوكول:", reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_"))
def set_port(call):
    user_creation_steps[call.from_user.id]['protocol'] = call.data.split("_")[1]
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("80 (WS)", callback_data="setport_80"),
          types.InlineKeyboardButton("443 (TLS)", callback_data="setport_443"))
    bot.edit_message_text("2️⃣ اختر المنفذ:", call.message.chat.id, call.message.message_id, reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data.startswith("setport_"))
def set_host_choice(call):
    user_creation_steps[call.from_user.id]['port'] = call.data.split("_")[1]
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton(f"استخدام IP السيرفر ({SERVER_IP})", callback_data="host_auto"),
          types.InlineKeyboardButton("إدخال IP يدوي", callback_data="host_manual"))
    bot.edit_message_text("3️⃣ اختر المضيف (Host):", call.message.chat.id, call.message.message_id, reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data.startswith("host_"))
def handle_host(call):
    if call.data == "host_auto":
        user_creation_steps[call.from_user.id]['host'] = SERVER_IP
        ask_path_step(call.message)
    else:
        msg = bot.send_message(call.message.chat.id, "اكتب الـ IP أو الدومين:")
        bot.register_next_step_handler(msg, save_manual_ip)

def save_manual_ip(message):
    user_creation_steps[message.from_user.id]['host'] = message.text
    ask_path_step(message)

def ask_path_step(message):
    msg = bot.send_message(message.chat.id, "4️⃣ أدخل المسار (Path) - مثال: `/v2ray`")
    bot.register_next_step_handler(msg, save_path_step)

def save_path_step(message):
    user_creation_steps[message.from_user.id]['path'] = message.text
    user_creation_steps[message.from_user.id]['uuid'] = str(uuid.uuid4())
    msg = bot.send_message(message.chat.id, "5️⃣ أدخل وصفاً مختصراً للكود:")
    bot.register_next_step_handler(msg, save_desc_step)

def save_desc_step(message):
    user_creation_steps[message.from_user.id]['description'] = message.text
    msg = bot.send_message(message.chat.id, "6️⃣ أرسل يوزر القناة مع @:")
    bot.register_next_step_handler(msg, set_channel_step)

def set_channel_step(message):
    user_creation_steps[message.from_user.id]['channel'] = message.text
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("❤️ تفاعل لايكات", callback_data="mode_like"),
          types.InlineKeyboardButton("⚡ نشر فوري", callback_data="mode_direct"))
    bot.send_message(message.chat.id, "✨ اختر طريقة النشر:", reply_markup=m)

@bot.callback_query_handler(func=lambda call: call.data.startswith("mode_"))
def handle_publish_mode(call):
    mode = call.data.split("_")[1]
    if mode == "like":
        msg = bot.send_message(call.message.chat.id, "أدخل عدد اللايكات المطلوبة:")
        bot.register_next_step_handler(msg, save_likes_and_finish)
    else:
        user_creation_steps[call.from_user.id]['target'] = 0
        execute_finish(call.from_user.id, call.message)

def save_likes_and_finish(message):
    user_creation_steps[message.from_user.id]['target'] = int(message.text)
    execute_finish(message.from_user.id, message)

def execute_finish(u_id, message):
    d = user_creation_steps[u_id]
    code = generate_v2ray_config(d['protocol'], d['uuid'], d['host'], d['port'], d['path'], "Premium_VPN")
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO tasks (protocol, port, path, uuid_str, host, channel, description, interaction_target) VALUES (?,?,?,?,?,?,?,?)",
              (d['protocol'], d['port'], d['path'], d['uuid'], d['host'], d['channel'], d['description'], d['target']))
    t_id = c.lastrowid
    conn.commit()

    if d['target'] > 0:
        txt = f"🎁 **كود {d['protocol'].upper()} جديد!**\n\n📝 الوصف: {d['description']}\n📊 المطلوب: {d['target']} تفاعل ❤️"
        mk = types.InlineKeyboardMarkup()
        mk.add(types.InlineKeyboardButton(f"❤️ دعم (0/{d['target']})", callback_data=f"hit_{t_id}"))
        sent = bot.send_message(d['channel'], txt, reply_markup=mk, parse_mode="Markdown")
        c.execute("UPDATE tasks SET interaction_msg_id = ?, interaction_chat_id = ? WHERE id = ?", (sent.message_id, sent.chat.id, t_id))
        conn.commit()
    else:
        pub = f"🚀 **كود اتصال جاهز!**\n\n📝 {d['description']}\n📡 النوع: {d['protocol'].upper()}\n🔌 المنفذ: {d['port']}\n━━━━━━━━━━━━━━\n`{code}`"
        bot.send_message(d['channel'], pub, parse_mode="Markdown")
    
    conn.close()
    bot.send_message(message.chat.id, "✅ تمت العملية بنجاح!")

# --- معالجة التفاعل ❤️ ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("hit_"))
def handle_hit(call):
    t_id = int(call.data.split("_")[1])
    u_id = call.from_user.id
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    try:
        c.execute("INSERT INTO interactions (task_id, user_id) VALUES (?, ?)", (t_id, u_id))
        c.execute("SELECT * FROM tasks WHERE id = ?", (t_id,))
        task = c.fetchone()
        new_count = task[12] + 1
        c.execute("UPDATE tasks SET interaction_current = ? WHERE id = ?", (new_count, t_id))
        conn.commit()
        
        if new_count >= task[11]:
            # اكتمال التفاعل - إرسال الكود
            final_code = generate_v2ray_config(task[1], task[4], task[5], task[2], task[3], "V2RAY_FREE")
            bot.edit_message_text(f"✅ **اكتمل التفاعل!**\n\n📝 {task[10]}\n━━━━━━━━━━━━━━\n`{final_code}`", task[14], task[13], parse_mode="Markdown")
        else:
            mk = types.InlineKeyboardMarkup()
            mk.add(types.InlineKeyboardButton(f"❤️ دعم ({new_count}/{task[11]})", callback_data=f"hit_{t_id}"))
            bot.edit_message_reply_markup(task[14], task[13], reply_markup=mk)
            
    except:
        bot.answer_callback_query(call.id, "❌ تفاعلت مسبقاً!")
    conn.close()

# --- إدارة وحذف ---
@bot.message_handler(func=lambda m: m.text == "📂 إدارة الكودات")
def manage(message):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, description FROM tasks ORDER BY id DESC LIMIT 5")
    for r in c.fetchall():
        m = types.InlineKeyboardMarkup()
        m.add(types.InlineKeyboardButton("🗑 حذف", callback_data=f"drop_{r[0]}"))
        bot.send_message(message.chat.id, f"ID: {r[0]} | {r[1]}", reply_markup=m)
    conn.close()

@bot.callback_query_handler(func=lambda call: call.data.startswith("drop_"))
def drop(call):
    tid = call.data.split("_")[1]
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM tasks WHERE id = ?", (tid,))
    conn.commit()
    conn.close()
    bot.delete_message(call.message.chat.id, call.message.message_id)

# --- تشغيل ---
if __name__ == "__main__":
    print("Bot is alive...")
    bot.infinity_polling()
