import telebot
from telebot import types
import sqlite3
import uuid
import json
import base64
import requests
import os
import threading
import time

# --- الإعدادات ---
BOT_TOKEN = "TOKEN_PLACEHOLDER"
ADMIN_ID = "ADMIN_ID_PLACEHOLDER"
bot = telebot.TeleBot(BOT_TOKEN)
DB_NAME = "srv_data_z77.db"

# جلب IP السيرفر
def get_ip():
    try: return requests.get('https://api.ipify.org', timeout=5).text
    except: return "127.0.0.1"
SERVER_IP = get_ip()

# --- تنظيف وإعادة ضبط (RM) ---
def clean_system():
    # حذف أي ملفات قديمة تسبب تداخل
    files_to_remove = ["old_data.tmp", "debug.log", "cache.json"]
    for f in files_to_remove:
        if os.path.exists(f):
            os.remove(f)
            print(f">>> Removed: {f}")

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        protocol TEXT, port TEXT, path TEXT, uuid_str TEXT,
        host TEXT, channel TEXT, description TEXT, 
        interaction_target INTEGER DEFAULT 0,
        interaction_current INTEGER DEFAULT 0,
        interaction_msg_id INTEGER DEFAULT 0,
        interaction_chat_id INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS interactions (
        task_id INTEGER, user_id INTEGER, UNIQUE(task_id, user_id)
    )''')
    conn.commit()
    conn.close()

clean_system()
user_cache = {}

# --- محرك إنشاء الروابط ---
def generate_link(p_type, u_id, host, port, path, name):
    path = path if path.startswith('/') else '/' + path
    security = "tls" if str(port) == "443" else "none"
    
    if p_type == "vmess":
        config = {"v":"2","ps":name,"add":host,"port":int(port),"id":u_id,"aid":"0","scy":"auto","net":"ws","type":"none","host":host,"path":path,"tls":security,"sni":host if security=="tls" else ""}
        return "vmess://" + base64.b64encode(json.dumps(config).encode()).decode()
    
    elif p_type == "vless":
        link = f"vless://{u_id}@{host}:{port}?encryption=none&security={security}&type=ws&host={host}&path={path}"
        if security == "tls": link += f"&sni={host}"
        return f"{link}#{name}"
    
    elif p_type == "trojan":
        link = f"trojan://{u_id}@{host}:{port}?security={security}&type=ws&host={host}&path={path}"
        if security == "tls": link += f"&sni={host}"
        return f"{link}#{name}"

# --- الأوامر ---
@bot.message_handler(commands=['start'])
def start_panel(message):
    if str(message.from_user.id) != str(ADMIN_ID): return
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add("🚀 إنشاء كود جديد", "📂 إدارة الكودات", "📊 إحصائيات", "🗑 تصفير البيانات")
    bot.send_message(message.chat.id, f"👑 **لوحة تحكم السيرفر (X-UI Edition)**\n━━━━━━━━━━━━━━\n🌐 IP: `{SERVER_IP}`\n━━━━━━━━━━━━━━\nتأكد من مطابقة الـ Port والـ Path في اللوحة.", reply_markup=m, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🚀 إنشاء كود جديد")
def step1(message):
    user_cache[message.from_user.id] = {}
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton("VMess", callback_data="p_vmess"),
           types.InlineKeyboardButton("VLESS", callback_data="p_vless"),
           types.InlineKeyboardButton("Trojan", callback_data="p_trojan"))
    bot.send_message(message.chat.id, "1️⃣ **اختر البروتوكول:**", reply_markup=mk, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("p_"))
def step2(call):
    user_cache[call.from_user.id]['proto'] = call.data.split("_")[1]
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton("80 (WS)", callback_data="pt_80"),
           types.InlineKeyboardButton("443 (TLS)", callback_data="pt_443"))
    bot.edit_message_text("2️⃣ **اختر المنفذ:**", call.message.chat.id, call.message.message_id, reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("pt_"))
def step3(call):
    user_cache[call.from_user.id]['port'] = call.data.split("_")[1]
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton(f"استخدام IP السيرفر ({SERVER_IP})", callback_data="h_auto"),
           types.InlineKeyboardButton("إدخال IP يدوي", callback_data="h_manual"))
    bot.edit_message_text("3️⃣ **عنوان الـ Host:**", call.message.chat.id, call.message.message_id, reply_markup=mk)

# (نظام التفاعل والحفظ والوصف...)
@bot.callback_query_handler(func=lambda c: c.data.startswith("h_"))
def step4(call):
    if "auto" in call.data:
        user_cache[call.from_user.id]['host'] = SERVER_IP
        ask_path(call.message)
    else:
        m = bot.send_message(call.message.chat.id, "ارسل الـ IP:")
        bot.register_next_step_handler(m, save_ip)

def save_ip(m):
    user_cache[m.from_user.id]['host'] = m.text
    ask_path(m)

def ask_path(m):
    msg = bot.send_message(m.chat.id, "4️⃣ **أدخل المسار (Path):**\nمثال: `/v2ray` (يجب أن يطابق لوحة X-UI)")
    bot.register_next_step_handler(msg, save_path)

def save_path(m):
    user_cache[m.from_user.id]['path'] = m.text
    user_cache[m.from_user.id]['uuid'] = str(uuid.uuid4())
    msg = bot.send_message(m.chat.id, "5️⃣ **وصف الكود:**")
    bot.register_next_step_handler(msg, save_desc)

def save_desc(m):
    user_cache[m.from_user.id]['desc'] = m.text
    msg = bot.send_message(m.chat.id, "6️⃣ **يوزر القناة (@...):**")
    bot.register_next_step_handler(msg, set_chan)

def set_chan(m):
    user_cache[m.from_user.id]['chan'] = m.text
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton("❤️ تفاعل لايك", callback_data="m_like"),
           types.InlineKeyboardButton("⚡ نشر فوري", callback_data="m_now"))
    bot.send_message(m.chat.id, "✨ **اختر نظام النشر:**", reply_markup=mk)

@bot.callback_query_handler(func=lambda c: c.data.startswith("m_"))
def finalize(call):
    if "like" in call.data:
        msg = bot.send_message(call.message.chat.id, "أدخل عدد التفاعلات:")
        bot.register_next_step_handler(msg, save_target)
    else:
        user_cache[call.from_user.id]['target'] = 0
        publish(call.from_user.id, call.message)

def save_target(m):
    user_cache[m.from_user.id]['target'] = int(m.text)
    publish(m.from_user.id, m)

def publish(u_id, message):
    d = user_cache[u_id]
    link = generate_link(d['proto'], d['uuid'], d['host'], d['port'], d['path'], "V2Ray_Premium")
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO tasks (protocol, port, path, uuid_str, host, channel, description, interaction_target) VALUES (?,?,?,?,?,?,?,?)",
              (d['proto'], d['port'], d['path'], d['uuid'], d['host'], d['chan'], d['desc'], d['target']))
    t_id = c.lastrowid
    conn.commit()

    if d['target'] > 0:
        txt = f"🎁 **كود {d['proto'].upper()} جديد!**\n\n📝 الوصف: {d['desc']}\n📊 المطلوب: {d['target']} تفاعل ❤️"
        mk = types.InlineKeyboardMarkup()
        mk.add(types.InlineKeyboardButton(f"❤️ دعم (0/{d['target']})", callback_data=f"hit_{t_id}"))
        sent = bot.send_message(d['chan'], txt, reply_markup=mk, parse_mode="Markdown")
        c.execute("UPDATE tasks SET interaction_msg_id = ?, interaction_chat_id = ? WHERE id = ?", (sent.message_id, sent.chat.id, t_id))
        conn.commit()
    else:
        bot.send_message(d['chan'], f"🚀 **كود جاهز:**\n\n`{link}`", parse_mode="Markdown")
    
    conn.close()
    bot.send_message(message.chat.id, "✅ تم النشر!")

# معالجة التفاعل ❤️ (نفس المنطق القديم المطور)
@bot.callback_query_handler(func=lambda call: call.data.startswith("hit_"))
def handle_hit(call):
    tid = int(call.data.split("_")[1])
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO interactions (task_id, user_id) VALUES (?, ?)", (tid, call.from_user.id))
        c.execute("SELECT * FROM tasks WHERE id = ?", (tid,))
        t = c.fetchone()
        new_c = t[9] + 1
        c.execute("UPDATE tasks SET interaction_current = ? WHERE id = ?", (new_c, tid))
        conn.commit()
        if new_c >= t[8]:
            l = generate_link(t[1], t[4], t[5], t[2], t[3], "V2RAY_FREE")
            bot.edit_message_text(f"✅ **تم اكتمال التفاعل!**\n\n`{l}`", t[11], t[10], parse_mode="Markdown")
        else:
            mk = types.InlineKeyboardMarkup()
            mk.add(types.InlineKeyboardButton(f"❤️ تفاعل ({new_c}/{t[8]})", callback_data=f"hit_{tid}"))
            bot.edit_message_reply_markup(t[11], t[10], reply_markup=mk)
    except:
        bot.answer_callback_query(call.id, "❌ تفاعلت مسبقاً!")
    conn.close()

if __name__ == "__main__":
    bot.infinity_polling()
