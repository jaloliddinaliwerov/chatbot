import os
import sqlite3
import telebot
from flask import Flask, request
from google import genai

# 1. Sozlamalar va Kalitlar
BOT_TOKEN = os.getenv("BOT_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")
PORT = int(os.environ.get('PORT', 8080))

bot = telebot.TeleBot(BOT_TOKEN)
ai_client = genai.Client(api_key=AI_API_KEY)
app = Flask(__name__)

DB_NAME = "metaverse_game.db"

# 2. Ma'lumotlar bazasini tashkil qilish
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Users jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            coins INTEGER DEFAULT 1000,
            xp INTEGER DEFAULT 0,
            energy INTEGER DEFAULT 100,
            is_admin BOOLEAN DEFAULT FALSE
        )
    ''')
    # Promokodlar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY,
            reward_coins INTEGER DEFAULT 0,
            reward_energy INTEGER DEFAULT 0,
            max_uses INTEGER DEFAULT 1,
            current_uses INTEGER DEFAULT 0
        )
    ''')
    # Ishlatilgan promokodlar tarixi (Bitta odam bir marta ishlatishi uchun)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS used_promos (
            telegram_id INTEGER,
            code TEXT,
            PRIMARY KEY (telegram_id, code)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_or_create_user(telegram_id, username):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT coins, xp, energy, is_admin FROM users WHERE telegram_id = ?", (telegram_id,))
    user = cursor.fetchone()
    
    if not user:
        # Boshlanishiga 1000$ pul va 100 energiya beriladi
        cursor.execute("INSERT INTO users (telegram_id, username, coins, xp, energy) VALUES (?, ?, 1000, 0, 100)", 
                       (telegram_id, username))
        conn.commit()
        cursor.execute("SELECT coins, xp, energy, is_admin FROM users WHERE telegram_id = ?", (telegram_id,))
        user = cursor.fetchone()
        
    conn.close()
    return {"coins": user[0], "xp": user[1], "energy": user[2], "is_admin": bool(user[3])}

# --- 🎮 FOYDALANUVCHILAR UCHUN BUYRUQLAR ---

@bot.message_handler(commands=['start'])
def start_cmd(message):
    chat_id = message.chat.id
    user = get_or_create_user(chat_id, message.from_user.username)
    
    admin_note = "\n\n⭐️ **Siz Adminsiz!** Yangi kod qo'shish: `/add_promo KOD PUL ENERGIYA LIMIT`" if user["is_admin"] else ""
    
    welcome = (
        "🏢 **AI Mega-Biznes Simulyatoriga xush kelibsiz!**\n\n"
        f"🪙 Balansingiz: **{user['coins']}$** | 🧠 Obro': {user['xp']} XP | ⚡ Energiya: {user['energy']}%\n\n"
        "📜 **Asosiy buyruqlar:**\n"
        "▶️ /play - AI Kvestni boshlash (Guruhda yoki shaxsiyda)\n"
        "🎒 /balance - Batafsil profil va status\n"
        "🔑 /promo [kod] - Promokodni faollashtirish"
        f"{admin_note}"
    )
    bot.send_message(chat_id, welcome, parse_mode="Markdown")

@bot.message_handler(commands=['balance'])
def balance_cmd(message):
    chat_id = message.chat.id
    user = get_or_create_user(chat_id, message.from_user.username)
    status = (
        "📊 **Sizning Biznes Profilingiz:**\n"
        f"💰 Naqd kapital: {user['coins']}$\n"
        f"🧠 Jamiyatdagi obro': {user['xp']} XP\n"
        f"⚡ Chidamlilik (Energiya): {user['energy']}%"
    )
    bot.send_message(chat_id, status, parse_mode="Markdown")

@bot.message_handler(commands=['promo'])
def use_promo(message):
    chat_id = message.chat.id
    user = get_or_create_user(chat_id, message.from_user.username)
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "❌ Kodni kiriting. Masalan: `/promo BIZNES2026`", parse_mode="Markdown")
        return
        
    promo_code = args[1].upper()
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Kod borligini tekshirish
    cursor.execute("SELECT reward_coins, reward_energy, max_uses, current_uses FROM promocodes WHERE code = ?", (promo_code,))
    promo = cursor.fetchone()
    
    if not promo:
        bot.reply_to(message, "❌ Bunday promokod mavjud emas yoki muddati tugagan.")
        conn.close()
        return
        
    reward_coins, reward_energy, max_uses, current_uses = promo
    
    # Limit tugaganini tekshirish
    if current_uses >= max_uses:
        bot.reply_to(message, "😢 Afsuski, bu promokodning faollashtirish limiti tugabdi.")
        conn.close()
        return
        
    # Oldin ishlatganini tekshirish
    cursor.execute("SELECT * FROM used_promos WHERE telegram_id = ? AND code = ?", (chat_id, promo_code))
    already_used = cursor.fetchone()
    
    if already_used:
        bot.reply_to(message, "⚠️ Siz bu promokodni bir marta ishlatib bo'lgansiz!")
        conn.close()
        return
        
    # Balansni yangilash va tarixga yozish
    cursor.execute("UPDATE users SET coins = coins + ?, energy = MIN(100, energy + ?) WHERE telegram_id = ?", 
                   (reward_coins, reward_energy, chat_id))
    cursor.execute("UPDATE promocodes SET current_uses = current_uses + 1 WHERE code = ?", (promo_code,))
    cursor.execute("INSERT INTO used_promos (telegram_id, code) VALUES (?, ?)", (chat_id, promo_code))
    
    conn.commit()
    conn.close()
    
    bot.reply_to(message, f"🎉 **Tabriklaymiz!**\n\nPromokod muvaffaqiyatli faollashdi:\n"
                          f"🪙 +{reward_coins}$ kapital berildi!\n⚡ +{reward_energy}% energiya qo'shildi!", parse_mode="Markdown")

# --- 👑 ADMIN BUYRUQLARI ---

@bot.message_handler(commands=['add_promo'])
def add_promo_cmd(message):
    chat_id = message.chat.id
    user = get_or_create_user(chat_id, message.from_user.username)
    
    # Adminlikni tekshirish
    if not user["is_admin"]:
        bot.reply_to(message, "❌ Bu buyruq faqat loyiha adminlari uchun.")
        return
        
    # Format: /add_promo KOD COINS ENERGY LIMIT
    args = message.text.split()
    if len(args) < 5:
        bot.reply_to(message, "⚠️ **Format xato.** Ishlatish:\n`/add_promo KOD PUL ENERGIYA LIMIT`\n\nMasalan: `/add_promo VIP777 5000 50 100`", parse_mode="Markdown")
        return
        
    code = args[1].upper()
    try:
        coins = int(args[2])
        energy = int(args[3])
        max_uses = int(args[4])
    except ValueError:
        bot.reply_to(message, "❌ Pul, energiya va limit faqat raqamlarda yozilishi kerak!")
        return
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO promocodes (code, reward_coins, reward_energy, max_uses) VALUES (?, ?, ?, ?)",
                       (code, coins, energy, max_uses))
        conn.commit()
        bot.reply_to(message, f"✅ **Yangi Promokod Yaratildi!**\n\n🔑 Kod: `{code}`\n🪙 Mukofot puli: {coins}$\n⚡ Mukofot energiyasi: {energy}%\n👥 Limit: {max_uses} kishi uchun.", parse_mode="Markdown")
    except sqlite3.IntegrityError:
        bot.reply_to(message, "❌ Bu nomdagi promokod bazada allaqachon bor! Boshqa nom tanlang.")
    finally:
        conn.close()

# --- 🤖 AI GAMEPLAY (GURUH VA SHAXSIY CHAT) ---

@bot.message_handler(commands=['play'])
def play_game(message):
    chat_id = message.chat.id
    user = get_or_create_user(chat_id, message.from_user.username)
    
    if user["energy"] < 10:
        bot.reply_to(message, "❌ O'yinni davom ettirishga energiyangiz yetarli emas (Kamida 10% kerak). Do'kondan energiya oling yoki biroz kuting.")
        return
        
    bot.send_chat_action(chat_id, 'typing')
    
    prompt = (
        "Siz iqtisodiy metaverse simulyatori Game Masterisiz. O'yinchiga qisqa (3 gapdan iborat), kutilmagan iqtisodiy yoki hayotiy krizis vaziyatini yarating. "
        f"O'yinchining hozirgi kapitali: {user['coins']}$, Obro'si: {user['xp']} XP. "
        "Unga variantlar bermang, keyingi harakatini o'z so'zlari bilan yozishini so'rang."
    )
    
    try:
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        
        # Energiyani 10% ga kamaytiramiz
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET energy = energy - 10 WHERE telegram_id = ?", (chat_id,))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"🎬 **YANGI SVOQEALIK (Sizdan 10% ⚡ ketdi):**\n\n{response.text}")
    except Exception as e:
        bot.reply_to(message, "AI hozir band, qaytadan urinib ko'ring.")

# --- 🌐 RAILWAY VEB-SERVER QISMI ---

@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    RAILWAY_APP_URL = os.getenv("RAILWAY_APP_URL") 
    if RAILWAY_APP_URL:
        bot.set_webhook(url=RAILWAY_APP_URL + '/' + BOT_TOKEN)
        return "Barcha tizimlar (Admin, Promokod, AI) tayyor!", 200
    return "URL xatosi", 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
