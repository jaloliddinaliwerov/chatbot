import os
import sqlite3
import telebot
import random
from flask import Flask, request
from google import genai

# 1. Sozlamalar va Kalitlar
BOT_TOKEN = os.getenv("BOT_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")
PORT = int(os.environ.get('PORT', 8080))

bot = telebot.TeleBot(BOT_TOKEN)
ai_client = genai.Client(api_key=AI_API_KEY)
app = Flask(__name__)

DB_NAME = "metaverse_large.db"

# 2. Ma'lumotlar bazasini kengaytirilgan holda tashkil qilish
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Foydalanuvchilar
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            coins INTEGER DEFAULT 5000,
            xp INTEGER DEFAULT 0,
            energy INTEGER DEFAULT 100,
            is_admin BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # Passiv aktivlar (Kripto-ferma, Data-markaz va h.k.)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_assets (
            telegram_id INTEGER,
            asset_name TEXT,
            hourly_revenue INTEGER,
            quantity INTEGER DEFAULT 0,
            PRIMARY KEY (telegram_id, asset_name)
        )
    ''')
    
    # Shaxsiy do'kon (O'yinchi ombordan olib, o'zi narx qo'yib sotadigan joyi)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_shop (
            telegram_id INTEGER,
            item_name TEXT,
            quantity INTEGER DEFAULT 0,
            my_price INTEGER DEFAULT 0,
            PRIMARY KEY (telegram_id, item_name)
        )
    ''')
    
    # Promokodlar
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY,
            reward_coins INTEGER DEFAULT 0,
            reward_energy INTEGER DEFAULT 0,
            max_uses INTEGER DEFAULT 1,
            current_uses INTEGER DEFAULT 0
        )
    ''')
    
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

# Tizimdagi global tovarlar va aktivlar narxlari (Ulgurji bozor)
WHOLESALE_MARKET = {
    "IPHONE": {"wholesale_price": 600, "market_min": 800, "market_max": 1300},
    "PLAYSTATION": {"wholesale_price": 400, "market_min": 500, "market_max": 900}
}

PASSIVE_ASSETS = {
    "KRIPTO_FERMA": {"price": 3000, "hourly": 150},
    "DATA_MARKAZ": {"price": 10000, "hourly": 600}
}

def get_or_create_user(telegram_id, username):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT coins, xp, energy, is_admin FROM users WHERE telegram_id = ?", (telegram_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (telegram_id, username, coins, xp, energy) VALUES (?, ?, 5000, 0, 100)", (telegram_id, username))
        conn.commit()
        user = (5000, 0, 100, False)
    conn.close()
    return {"coins": user[0], "xp": user[1], "energy": user[2], "is_admin": bool(user[3])}

# --- 🔄 PASSIV DAROMADNI HISOBLASH FUNKSIYASI ---
def collect_passive_income(telegram_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT hourly_revenue, quantity FROM user_assets WHERE telegram_id = ?", (telegram_id,))
    assets = cursor.fetchall()
    
    total_income = 0
    for hourly, qty in assets:
        total_income += (hourly * qty) # Silliqlik uchun har safar buyruq berganda daromad qo'shiladi
        
    if total_income > 0:
        cursor.execute("UPDATE users SET coins = coins + ? WHERE telegram_id = ?", (total_income, telegram_id))
        conn.commit()
    conn.close()
    return total_income

# --- 🎮 ASOSIY MENU KODLARI ---

@bot.message_handler(commands=['start'])
def start_cmd(message):
    chat_id = message.chat.id
    user = get_or_create_user(chat_id, message.from_user.username)
    income = collect_passive_income(chat_id)
    
    income_msg = f"🪙 Ofline bo'lganingizda aktivlaringiz sizga **+{income}$** olib keldi!\n\n" if income > 0 else ""
    admin_note = "⭐️ **Siz Adminsiz!** Promokod qo'shish: `/add_promo KOD PUL ENERGIYA LIMIT`" if user["is_admin"] else ""
    
    welcome = (
        "🏙 **AI MULTI-BIZNES METAVERSE** 🏙\n\n"
        f"{income_msg}"
        f"💰 Kapital: **{user['coins']}$** | 🧠 Obro': {user['xp']} XP | ⚡ Energiya: {user['energy']}%\n\n"
        "🛒 **DO'KON VA BOZOR TIZIMI:**\n"
        "🏬 /market - Ulgurji bozor (Optom tovarlar va Kripto-fermalar sotib olish)\n"
        "🎒 /my_shop - Shaxsiy do'koningiz (Tovar narxini o'zingiz qo'yib sotish)\n"
        "📈 /sell_retail - Do'kondagi tovarlarni AI mijozlarga sotishni boshlash\n\n"
        "🎮 **O'YIN LOGIKASI:**\n"
        "▶️ /play - Tasodifiy AI Kvest (Vaziyatlar)\n"
        "🔑 /promo [kod] - Promokod ishlash\n"
        f"{admin_note}"
    )
    bot.send_message(chat_id, welcome, parse_mode="Markdown")

# --- 🏬 ULGERJI BOZOR (MARKET) ---
@bot.message_handler(commands=['market'])
def market_cmd(message):
    chat_id = message.chat.id
    collect_passive_income(chat_id)
    
    text = (
        "🏬 **ULGURJI BOZOR VA INVESTITSIYALAR**\n\n"
        "📦 **Optom tovarlar (Arzon olib shaxsiy do'konda qimmat sotish uchun):**\n"
        "🔹 `/buy_wholesale IPHONE` — Bahosi: 600$\n"
        "🔹 `/buy_wholesale PLAYSTATION` — Bahosi: 400$\n\n"
        "⚡ **Passiv daromad keltiruvchi aktivlar:**\n"
        "⛏ `/buy_asset KRIPTO_FERMA` — Bahosi: 3000$ (Soatiga +150$ beradi)\n"
        "🏢 `/buy_asset DATA_MARKAZ` — Bahosi: 10000$ (Soatiga +600$ beradi)"
    )
    bot.send_message(chat_id, text, parse_mode="Markdown")

@bot.message_handler(commands=['buy_wholesale'])
def buy_wholesale_cmd(message):
    chat_id = message.chat.id
    user = get_or_create_user(chat_id, message.from_user.username)
    args = message.text.split()
    
    if len(args) < 2:
        bot.reply_to(message, "Tovar nomini yozing. Masalan: `/buy_wholesale IPHONE`")
        return
        
    item = args[1].upper()
    if item not in WHOLESALE_MARKET:
        bot.reply_to(message, "❌ Bunday tovar ulgurji bozorda yo'q.")
        return
        
    cost = WHOLESALE_MARKET[item]["wholesale_price"]
    if user["coins"] < cost:
        bot.reply_to(message, "❌ Mablag'ingiz yetarli emas!")
        return
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET coins = coins - ? WHERE telegram_id = ?", (cost, chat_id))
    cursor.execute("INSERT INTO user_shop (telegram_id, item_name, quantity, my_price) VALUES (?, ?, 1, 0) "
                   "ON CONFLICT(telegram_id, item_name) DO UPDATE SET quantity = quantity + 1", (chat_id, item))
    conn.commit()
    conn.close()
    
    bot.reply_to(message, f"✅ Siz muvaffaqiyatli 1 dona **{item}**ni ulgurji narxda sotib oldingiz! Endi uni `/my_shop` orqali narxini belgilab soting.")

@bot.message_handler(commands=['buy_asset'])
def buy_asset_cmd(message):
    chat_id = message.chat.id
    user = get_or_create_user(chat_id, message.from_user.username)
    args = message.text.split()
    
    if len(args) < 2:
        bot.reply_to(message, "Aktiv nomini yozing. Masalan: `/buy_asset KRIPTO_FERMA`")
        return
        
    asset = args[1].upper()
    if asset not in PASSIVE_ASSETS:
        bot.reply_to(message, "❌ Bunday aktiv yo'q.")
        return
        
    cost = PASSIVE_ASSETS[asset]["price"]
    hourly = PASSIVE_ASSETS[asset]["hourly"]
    
    if user["coins"] < cost:
        bot.reply_to(message, "❌ Pulingiz yetarli emas!")
        return
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET coins = coins - ? WHERE telegram_id = ?", (cost, chat_id))
    cursor.execute("INSERT INTO user_assets (telegram_id, asset_name, hourly_revenue, quantity) VALUES (?, ?, ?, 1) "
                   "ON CONFLICT(telegram_id, asset_name) DO UPDATE SET quantity = quantity + 1", (chat_id, asset, hourly))
    conn.commit()
    conn.close()
    
    bot.reply_to(message, f"🚀 Tabriklaymiz! **{asset}** sotib olindi. Endi u sizga har soatda passiv daromad keltiradi!")

# --- 🎒 SHAXSIY DO'KON VA NARX BELGILASH ---
@bot.message_handler(commands=['my_shop'])
def my_shop_cmd(message):
    chat_id = message.chat.id
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT item_name, quantity, my_price FROM user_shop WHERE telegram_id = ?", (chat_id,))
    items = cursor.fetchall()
    conn.close()
    
    if not items:
        bot.send_message(chat_id, "🎒 Shaxsiy do'koningiz hozircha bo'sh. Bozorga borib optom tovar oling: /market")
        return
        
    text = "🎒 **Sizning Shaxsiy Do'koningiz va Omboringiz:**\n\n"
    for name, qty, price in items:
        text += f"📦 **{name}** — Soni: {qty} ta | Siz qo'ygan sotuv narxi: {price}$\n"
        text += f"✍️ Narx belgilash uchun: `/set_price {name} [narx]`\n\n"
    text += "📈 Do'kondagi hamma narsani chakana bozorga sotuvga chiqarish: /sell_retail"
    bot.send_message(chat_id, text, parse_mode="Markdown")

@bot.message_handler(commands=['set_price'])
def set_price_cmd(message):
    chat_id = message.chat.id
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "Format xato. Masalan: `/set_price IPHONE 1100`")
        return
        
    item = args[1].upper()
    try:
        price = int(args[2])
    except ValueError:
        bot.reply_to(message, "❌ Narx faqat raqam bo'lishi kerak!")
        return
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE user_shop SET my_price = ? WHERE telegram_id = ? AND item_name = ?", (price, chat_id, item))
    conn.commit()
    conn.close()
    bot.reply_to(message, f"✅ **{item}** uchun chakana sotuv narxi **{price}$** qilib belgilandi!")

# --- 📈 AI MIJOZLARGA CHAKANA SOTISH (RETAIL LOGIC) ---
@bot.message_handler(commands=['sell_retail'])
def sell_retail_cmd(message):
    chat_id = message.chat.id
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT item_name, quantity, my_price FROM user_shop WHERE telegram_id = ? AND quantity > 0", (chat_id,))
    items = cursor.fetchall()
    
    if not items:
        bot.reply_to(message, "❌ Sotish uchun do'konda tovaringiz yo'q.")
        conn.close()
        return
        
    bot.send_chat_action(chat_id, 'typing')
    
    total_profit = 0
    sales_report = "📊 **Chakana savdo yakunlari (AI Mijozlar tahlili):**\n\n"
    
    for name, qty, my_price in items:
        min_p = WHOLESALE_MARKET[name]["market_min"]
        max_p = WHOLESALE_MARKET[name]["market_max"]
        
        # Narx optimalmi yoki juda qimmatmi, tekshiramiz
        if my_price == 0:
            sales_report += f"⚠️ **{name}**ga narx qo'ymagansiz, xaridorlar sotib olmadi.\n"
        elif my_price > max_p:
            sales_report += f"❌ **{name}** juda qimmat ({my_price}$)! AI mijozlar boshqa do'kondan sotib olishdi.\n"
        elif my_price < min_p:
            # Arzon qo'yib yuborgan bo'lsa darrov sotiladi lekin foyda kam
            revenue = my_price * qty
            total_profit += revenue
            cursor.execute("UPDATE user_shop SET quantity = 0 WHERE telegram_id = ? AND item_name = ?", (chat_id, name))
            sales_report += f"💸 **{name}**ni juda arzon sotdingiz! Soni: {qty} ta | Tushum: {revenue}$\n"
        else:
            # Optimal narx - hammasi muvaffaqiyatli sotiladi
            revenue = my_price * qty
            total_profit += revenue
            cursor.execute("UPDATE user_shop SET quantity = 0 WHERE telegram_id = ? AND item_name = ?", (chat_id, name))
            sales_report += f"🎉 Muvaffaqiyatli savdo! **{name}** optimal narxda sotildi! Tushum: {revenue}$\n"
            cursor.execute("UPDATE users SET xp = xp + 15 WHERE telegram_id = ?", (chat_id,)) # Obro' oshadi
            
    if total_profit > 0:
        cursor.execute("UPDATE users SET coins = coins + ? WHERE telegram_id = ?", (total_profit, chat_id))
        sales_report += f"\n🪙 Jami hisobingizga qo'shildi: **{total_profit}$**"
        
    conn.commit()
    conn.close()
    bot.send_message(chat_id, sales_report, parse_mode="Markdown")

# --- 🤖 AI GAMEPLAY (KVESTLAR) ---
@bot.message_handler(commands=['play'])
def play_game(message):
    chat_id = message.chat.id
    user = get_or_create_user(chat_id, message.from_user.username)
    
    if user["energy"] < 10:
        bot.reply_to(message, "❌ Energiyangiz kam! Biroz kuting yoki /promo orqali energiya oling.")
        return
        
    bot.send_chat_action(chat_id, 'typing')
    
    prompt = (
        "Siz iqtisodiy va kiber-biznes simulyatori Game Masterisiz. O'yinchiga qisqa (3 gapdan iborat), "
        "kutilmagan biznes inqirozi yoki krizisli ssenariy yarating. Variantlar bermang, o'z javobini erkin yozishini so'rang."
    )
    
    try:
        response = ai_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET energy = energy - 10 WHERE telegram_id = ?", (chat_id,))
        conn.commit()
        conn.close()
        bot.reply_to(message, f"🎬 **Krizisli kvest (Energiya -10% ⚡):**\n\n{response.text}")
    except Exception:
        bot.reply_to(message, "AI hozir band.")

# --- 🔑 ADMIN VA PROMOKOD LOGIKASI ---
@bot.message_handler(commands=['promo'])
def use_promo(message):
    chat_id = message.chat.id
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Kod kiriting: `/promo KOD`")
        return
    promo_code = args[1].upper()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT reward_coins, reward_energy, max_uses, current_uses FROM promocodes WHERE code = ?", (promo_code,))
    promo = cursor.fetchone()
    if not promo:
        bot.reply_to(message, "❌ Bunday promokod yo'q.")
        conn.close()
        return
    reward_coins, reward_energy, max_uses, current_uses = promo
    if current_uses >= max_uses:
        bot.reply_to(message, "❌ Kod limiti tugagan.")
        conn.close()
        return
    cursor.execute("SELECT * FROM used_promos WHERE telegram_id = ? AND code = ?", (chat_id, promo_code))
    if cursor.fetchone():
        bot.reply_to(message, "⚠️ Siz buni ishlatgansiz.")
        conn.close()
        return
    cursor.execute("UPDATE users SET coins = coins + ?, energy = MIN(100, energy + ?) WHERE telegram_id = ?", (reward_coins, reward_energy, chat_id))
    cursor.execute("UPDATE promocodes SET current_uses = current_uses + 1 WHERE code = ?", (promo_code,))
    cursor.execute("INSERT INTO used_promos (telegram_id, code) VALUES (?, ?)", (chat_id, promo_code))
    conn.commit()
    conn.close()
    bot.reply_to(message, f"🎉 Faollashdi! +{reward_coins}$ | +{reward_energy}% ⚡")

@bot.message_handler(commands=['add_promo'])
def add_promo_cmd(message):
    chat_id = message.chat.id
    user = get_or_create_user(chat_id, message.from_user.username)
    if not user["is_admin"]: return
    args = message.text.split()
    if len(args) < 5: return
    code = args[1].upper()
    coins, energy, limit = int(args[2]), int(args[3]), int(args[4])
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO promocodes (code, reward_coins, reward_energy, max_uses) VALUES (?, ?, ?, ?)", (code, coins, energy, limit))
    conn.commit()
    conn.close()
    bot.reply_to(message, f"✅ Promokod qo'shildi: {code}")

# --- 🌐 WEBHOOK ENGINE ---
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
        return "Masshtabli iqtisodiy metaverse bot tayyor!", 200
    return "URL xatosi", 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
