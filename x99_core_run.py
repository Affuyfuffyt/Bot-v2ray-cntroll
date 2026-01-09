import telebot
from telebot import types
import sqlite3
import uuid
import json
import base64
import time
import threading
import schedule
import os
import random

# --- تكوين البوت ---
# سيقوم سكربت التثبيت باستبدال هذه القيم تلقائياً
BOT_TOKEN = "TOKEN_PLACEHOLDER"
ADMIN_ID = "ADMIN_ID_PLACEHOLDER"

bot = telebot.TeleBot(BOT_TOKEN)

# --- قاعدة البيانات ---
DB_NAME = "srv_data_z77.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # جدول المهام المنشورة
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        protocol TEXT,
        port TEXT,
        path TEXT,
        uuid_str TEXT,
        host TEXT,
        quota TEXT,
        users_limit TEXT,
        duration TEXT,
        channel TEXT,
        description TEXT,
        interaction_target INTEGER DEFAULT 0,
        interaction_current INTEGER DEFAULT 0,
        interaction_msg_id INTEGER DEFAULT 0,
        interaction_chat_id INTEGER DEFAULT 0,
        status TEXT DEFAULT 'active' 
    )''')
    # جدول لتتبع من ضغط على زر التفاعل (لمنع التكرار)
    c.execute('''CREATE TABLE IF NOT EXISTS interactions (
        task_id INTEGER,
        user_id INTEGER,
        UNIQUE(task_id, user_id)
    )''')
    conn.commit()
    conn.close()

init_db()

# --- مخزن مؤقت لبيانات الإنشاء (User Session) ---
user_creation_steps = {}

# --- دوال مساعدة لتوليد الروابط ---
def generate_vmess(uuid_str, host, port, path, name):
    conf = {
        "v": "2", "ps": name, "add": host, "port": port, "id": uuid_str,
        "aid": "0", "scy": "auto", "net": "ws", "type": "none", "host": host,
        "path": path, "tls": "tls", "sni": host, "alpn": ""
    }
    json_conf = json.dumps(conf)
    return "vmess://" + base64.b64encode(json_conf.encode('utf-8')).decode('utf-8')

def generate_vless(uuid_str, host, port, path, name):
    return f"vless://{uuid_str}@{host}:{port}?encryption=none&security=tls&type=ws&host={host}&path={path}#{name}"

def generate_trojan(uuid_str, host, port, path, name):
    return f"trojan://{uuid_str}@{host}:{port}?security=tls&type=ws&host={host}&path={path}#{name}"

def generate_shadowsocks(uuid_str, host, port, path, name):
    # SS with v2ray-plugin simulation string
    cred = f"aes-256-gcm:{uuid_str}"
    b64_cred = base64.b64encode(cred.encode('utf-8')).decode('utf-8')
    return f"ss://{b64_cred}@{host}:{port}?plugin=v2ray-plugin%3Btls%3Bhost%3D{host}%3Bpath%3D{path}#{name}"

# --- القوائم والتحكم ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return # لا ترد على غير الأدمن
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton("⚙️ الإعدادات")
    btn2 = types.KeyboardButton("📂 الكودات المنشورة")
    markup.add(btn1, btn2)
    bot.send_message(message.chat.id, "👋 أهلاً بك في لوحة تحكم السيرفر.", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "⚙️ الإعدادات")
def settings_menu(message):
    if str(message.from_user.id) != str(ADMIN_ID): return
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton("🚀 إنشاء كود نشر تلقائي", callback_data="create_new")
    markup.add(btn)
    bot.send_message(message.chat.id, "قائمة الإعدادات:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📂 الكودات المنشورة")
def list_published_codes(message):
    if str(message.from_user.id) != str(ADMIN_ID): return
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, protocol, description, status, interaction_target, interaction_current FROM tasks")
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        bot.send_message(message.chat.id, "لا توجد كودات منشورة حالياً.")
        return

    for row in rows:
        t_id, proto, desc, status, target, current = row
        status_icon = "🟢" if status == 'active' else "🔴"
        interact_info = f" | تفاعل: {current}/{target}" if target > 0 else ""
        msg = f"{status_icon} ID: {t_id} | {proto}\nوصف: {desc}\n{interact_info}"
        
        markup = types.InlineKeyboardMarkup()
        btn_del = types.InlineKeyboardButton("🗑 حذف", callback_data=f"del_{t_id}")
        btn_stop = types.InlineKeyboardButton("⏸ إيقاف/تفعيل", callback_data=f"toggle_{t_id}")
        markup.add(btn_stop, btn_del)
        bot.send_message(message.chat.id, msg, reply_markup=markup)

# --- معالج الخطوات (Wizard) ---

@bot.callback_query_handler(func=lambda call: call.data == "create_new")
def step_1_protocol(call):
    user_creation_steps[call.from_user.id] = {} # Reset
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("VMess", callback_data="proto_vmess"),
        types.InlineKeyboardButton("VLESS", callback_data="proto_vless"),
        types.InlineKeyboardButton("Trojan", callback_data="proto_trojan"),
        types.InlineKeyboardButton("Shadowsocks", callback_data="proto_ss")
    )
    bot.edit_message_text("1️⃣ اختر نوع البروتوكول (WS):", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("proto_"))
def step_2_port(call):
    proto = call.data.split("_")[1]
    user_creation_steps[call.from_user.id]['protocol'] = proto
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("80", callback_data="port_80"),
        types.InlineKeyboardButton("443", callback_data="port_443"),
        types.InlineKeyboardButton("2053", callback_data="port_2053"),
        types.InlineKeyboardButton("✏️ كتابة يدوي", callback_data="port_manual")
    )
    bot.edit_message_text(f"✅ تم اختيار {proto}.\n2️⃣ اختر المنفذ (Port):", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("port_"))
def step_3_path_pre(call):
    selection = call.data.split("_")[1]
    if selection == "manual":
        msg = bot.send_message(call.message.chat.id, "اكتب رقم البورت الآن:")
        bot.register_next_step_handler(msg, step_3_path_manual_input)
    else:
        user_creation_steps[call.from_user.id]['port'] = selection
        step_3_path_ask(call.message.chat.id, call.from_user.id)

def step_3_path_manual_input(message):
    user_creation_steps[message.from_user.id]['port'] = message.text
    step_3_path_ask(message.chat.id, message.from_user.id)

def step_3_path_ask(chat_id, user_id):
    msg = bot.send_message(chat_id, "3️⃣ اكتب مسار الاتصال (Path) - (مثلاً /ws):")
    bot.register_next_step_handler(msg, step_4_uuid_pre)

def step_4_uuid_pre(message):
    user_creation_steps[message.from_user.id]['path'] = message.text
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🎲 عشوائي", callback_data="uuid_random"),
        types.InlineKeyboardButton("✏️ يدوي", callback_data="uuid_manual")
    )
    bot.send_message(message.chat.id, "4️⃣ اختيار UUID:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("uuid_"))
def step_5_host_pre(call):
    selection = call.data.split("_")[1]
    user_id = call.from_user.id
    if selection == "random":
        user_creation_steps[user_id]['uuid'] = str(uuid.uuid4())
        step_5_host_ask(call.message.chat.id, user_id)
    else:
        msg = bot.send_message(call.message.chat.id, "اكتب الـ UUID الآن:")
        bot.register_next_step_handler(msg, step_5_host_manual_save)

def step_5_host_manual_save(message):
    user_creation_steps[message.from_user.id]['uuid'] = message.text
    step_5_host_ask(message.chat.id, message.from_user.id)

def step_5_host_ask(chat_id, user_id):
    msg = bot.send_message(chat_id, "5️⃣ اكتب الـ Host/SNI (دومين أو آي بي):")
    bot.register_next_step_handler(msg, step_6_quota)

def step_6_quota(message):
    user_creation_steps[message.from_user.id]['host'] = message.text
    msg = bot.send_message(message.chat.id, "6️⃣ حدد كمية البيانات (مثلاً: 1GB, 500MB, 1TB):")
    bot.register_next_step_handler(msg, step_7_users)

def step_7_users(message):
    user_creation_steps[message.from_user.id]['quota'] = message.text
    msg = bot.send_message(message.chat.id, "7️⃣ حدد عدد المستخدمين المسموح (مثلاً: 1, 5, unlimited):")
    bot.register_next_step_handler(msg, step_8_duration)

def step_8_duration(message):
    user_creation_steps[message.from_user.id]['users_limit'] = message.text
    msg = bot.send_message(message.chat.id, "8️⃣ مدة صلاحية الكود (مثلاً: 30 يوم، 12 ساعة):")
    bot.register_next_step_handler(msg, step_9_channel)

def step_9_channel(message):
    user_creation_steps[message.from_user.id]['duration'] = message.text
    msg = bot.send_message(message.chat.id, "9️⃣ أرسل معرف القناة أو الرابط (مثلاً @MyChannel):")
    bot.register_next_step_handler(msg, step_10_desc)

def step_10_desc(message):
    user_creation_steps[message.from_user.id]['channel'] = message.text
    msg = bot.send_message(message.chat.id, "🔟 اكتب وصفاً للكود ليظهر في المنشور:")
    bot.register_next_step_handler(msg, step_11_interaction_ask)

def step_11_interaction_ask(message):
    user_creation_steps[message.from_user.id]['description'] = message.text
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("❤️ إضافة شرط تفاعل", callback_data="interact_yes"),
        types.InlineKeyboardButton("⏩ تخطي (نشر مباشر)", callback_data="interact_no")
    )
    bot.send_message(message.chat.id, "✨ هل تريد إضافة زر تفاعل (شرط للنشر)؟", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("interact_"))
def step_12_finalize(call):
    choice = call.data.split("_")[1]
    user_id = call.from_user.id
    
    if choice == "yes":
        msg = bot.send_message(call.message.chat.id, "اكتب عدد التفاعلات المطلوبة (مثلاً 20):")
        bot.register_next_step_handler(msg, step_13_save_with_interaction)
    else:
        # نشر مباشر
        save_and_publish(user_id, interaction=False)
        bot.send_message(call.message.chat.id, "✅ تم حفظ المهمة والنشر المباشر.")

def step_13_save_with_interaction(message):
    try:
        count = int(message.text)
        user_creation_steps[message.from_user.id]['target_count'] = count
        save_and_publish(message.from_user.id, interaction=True)
        bot.send_message(message.chat.id, f"✅ تم الحفظ. سيتم نشر بوست التفاعل وعند وصول {count} سيتم نشر الكود.")
    except ValueError:
        bot.send_message(message.chat.id, "أرقام فقط.")

# --- منطق الحفظ والنشر ---

def save_and_publish(user_id, interaction=False):
    data = user_creation_steps[user_id]
    
    # توليد الكود
    protocol = data['protocol']
    if protocol == "vmess":
        code = generate_vmess(data['uuid'], data['host'], data['port'], data['path'], "FreeVmess")
    elif protocol == "vless":
        code = generate_vless(data['uuid'], data['host'], data['port'], data['path'], "FreeVless")
    elif protocol == "trojan":
        code = generate_trojan(data['uuid'], data['host'], data['port'], data['path'], "FreeTrojan")
    elif protocol == "ss":
        code = generate_shadowsocks(data['uuid'], data['host'], data['port'], data['path'], "FreeSS")
    
    full_text_code = (
        f"🚀 **New {protocol.upper()} Config**\n\n"
        f"📶 Protocol: {protocol}\n"
        f"💾 Quota: {data['quota']}\n"
        f"👥 Users: {data['users_limit']}\n"
        f"⏳ Duration: {data['duration']}\n"
        f"📝 {data['description']}\n\n"
        f"🔗 Code:\n`{code}`"
    )

    interaction_target = data.get('target_count', 0) if interaction else 0
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''INSERT INTO tasks 
        (protocol, port, path, uuid_str, host, quota, users_limit, duration, channel, description, interaction_target)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
        (data['protocol'], data['port'], data['path'], data['uuid'], data['host'], data['quota'], data['users_limit'], data['duration'], data['channel'], data['description'], interaction_target))
    task_id = c.lastrowid
    conn.commit()

    # النشر للقناة
    channel_id = data['channel']
    
    if interaction:
        # نشر بوست التفاعل
        interact_text = (
            f"🔒 **محتوى حصري ({protocol.upper()})**\n\n"
            f"📝 الوصف: {data['description']}\n"
            f"💾 الحجم: {data['quota']}\n\n"
            f"👇 اضغط على الزر أدناه لنشر الكود!"
        )
        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton(f"❤️ دعم (0/{interaction_target})", callback_data=f"like_{task_id}")
        markup.add(btn)
        
        try:
            sent_msg = bot.send_message(channel_id, interact_text, reply_markup=markup, parse_mode="Markdown")
            c.execute("UPDATE tasks SET interaction_msg_id = ?, interaction_chat_id = ? WHERE id = ?", (sent_msg.message_id, sent_msg.chat.id, task_id))
            conn.commit()
        except Exception as e:
            bot.send_message(user_id, f"❌ خطأ في النشر للقناة: {e}")
    else:
        # نشر مباشر
        try:
            bot.send_message(channel_id, full_text_code, parse_mode="Markdown")
        except Exception as e:
            bot.send_message(user_id, f"❌ خطأ في النشر للقناة: {e}")
            
    conn.close()

# --- معالجة التفاعل (زر القلب) ---

@bot.callback_query_handler(func=lambda call: call.data.startswith("like_"))
def handle_like_click(call):
    task_id = int(call.data.split("_")[1])
    user_id = call.from_user.id
    
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # التحقق من البيانات
    c.execute("SELECT interaction_target, interaction_current, description, protocol, port, path, uuid_str, host, quota, users_limit, duration FROM tasks WHERE id = ?", (task_id,))
    task = c.fetchone()
    
    if not task:
        bot.answer_callback_query(call.id, "هذا المنشور قديم أو محذوف.")
        conn.close()
        return

    target, current, desc, proto, port, path, uuid_str, host, quota, u_lim, dur = task
    
    # التحقق هل المستخدم ضغط سابقاً
    try:
        c.execute("INSERT INTO interactions (task_id, user_id) VALUES (?, ?)", (task_id, user_id))
        new_current = current + 1
        c.execute("UPDATE tasks SET interaction_current = ? WHERE id = ?", (new_current, task_id))
        conn.commit()
        
        # تحديث الزر
        if new_current < target:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(f"❤️ دعم ({new_current}/{target})", callback_data=f"like_{task_id}"))
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
            bot.answer_callback_query(call.id, "❤️ شكراً لتفاعلك!")
        else:
            # تم الوصول للهدف! نشر الكود
            if proto == "vmess":
                code = generate_vmess(uuid_str, host, port, path, "FreeVmess")
            elif proto == "vless":
                code = generate_vless(uuid_str, host, port, path, "FreeVless")
            elif proto == "trojan":
                code = generate_trojan(uuid_str, host, port, path, "FreeTrojan")
            elif proto == "ss":
                code = generate_shadowsocks(uuid_str, host, port, path, "FreeSS")
            
            final_msg = (
                f"✅ **تم اكتمال التفاعل!**\n\n"
                f"🚀 Protocol: {proto}\n"
                f"📝 {desc}\n"
                f"💾 Quota: {quota} | ⏳ {dur}\n\n"
                f"👇 **Code:**\n`{code}`"
            )
            
            # حذف الزر وتعديل الرسالة أو إرسال جديد
            bot.edit_message_text(final_msg, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            bot.answer_callback_query(call.id, "✅ تم نشر الكود!")
            
    except sqlite3.IntegrityError:
        bot.answer_callback_query(call.id, "لقد تفاعلت بالفعل مع هذا المنشور!")
    
    conn.close()

# --- إدارة الكودات المنشورة ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("del_"))
def delete_task(call):
    t_id = call.data.split("_")[1]
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM tasks WHERE id=?", (t_id,))
    conn.commit()
    conn.close()
    bot.answer_callback_query(call.id, "تم الحذف")
    bot.delete_message(call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("toggle_"))
def toggle_task(call):
    t_id = call.data.split("_")[1]
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT status FROM tasks WHERE id=?", (t_id,))
    res = c.fetchone()
    if res:
        new_status = 'inactive' if res[0] == 'active' else 'active'
        c.execute("UPDATE tasks SET status=? WHERE id=?", (new_status, t_id))
        conn.commit()
        bot.answer_callback_query(call.id, f"تم تغيير الحالة إلى {new_status}")
    conn.close()

# --- تشغيل البوت ---
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    # تشغيل الخيوط الخلفية إذا كان هناك جدولة
    t = threading.Thread(target=run_scheduler)
    t.start()
    
    print("Bot is running...")
    bot.infinity_polling()
