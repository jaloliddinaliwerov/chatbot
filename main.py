import os
import telebot
from flask import Flask, request
from google import genai

BOT_TOKEN = os.getenv("BOT_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")
PORT = int(os.environ.get('PORT', 8080))

bot = telebot.TeleBot(BOT_TOKEN)
ai_client = genai.Client(api_key=AI_API_KEY)
app = Flask(__name__)

# O'yinchilarning ma'lumotlarini va o'yin tarixini saqlash uchun vaqtinchalik xotira (Dictionary)
# Keyinchalik buni ma'lumotlar bazasiga (Database) ko'chiramiz
user_games = {}

@bot.message_handler(commands=['start', 'help'])
def start_message(message):
    welcome = (
        "👋 AI Detektiv o'yiniga xush kelibsiz!\n\n"
        "Men sizga har safar mutlaqo yangi va sirli jinoyat ssenariysini yaratib beraman. "
        "Siz gumonlanuvchilarni so'roq qilib, haqiqiy qotilni topishingiz kerak!\n\n"
        "🎮 O'yinni boshlash uchun /play buyrug'ini yuboring."
    )
    bot.reply_to(message, welcome)

@bot.message_handler(commands=['play'])
def start_game(message):
    chat_id = message.chat.id
    bot.send_chat_action(chat_id, 'typing')
    
    # Yangi ssenariy yaratish uchun AI ga topshiriq
    prompt = (
        "Siz sirli detektiv o'yinlari ustasisiz. Menga yangi qisqa o'yin ssenariysi yarating. "
        "Undan 1 ta qurbon, jinoyat joyi va 3 ta bir-birini ayblayotgan aniq ismli gumonlanuvchi bo'lsin. "
        "Qotil kimligini menga hozircha aytmang, uni ichingizda sir saqlang. "
        "O'yinchiga qisqa va qiziqarli qilib voqeani tushuntiring va so'roqni boshlashini ayting."
    )
    
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        # O'yinchining tarixini boshlaymiz va ssenariyni xotiraga yozamiz
        user_games[chat_id] = {
            "history": [
                {"role": "user", "parts": [prompt]},
                {"role": "model", "parts": [response.text]}
            ]
        }
        
        bot.send_message(chat_id, f"🔍 **YANGI JINOYAT ISHI:**\n\n{response.text}\n\n"
                                  "✍️ *Gumonlanuvchilardan birini ismini aytib, unga savol bering (Masalan: 'Oshpaz, o'sha vaqtda qayerda edingiz?') yoki qotilni topgan bo'lsangiz 'Qotil - [Ism]' deb yozing.*")
    except Exception as e:
        bot.reply_to(message, "O'yinni boshlashda xatolik bo'ldi, qaytadan /play bosing.")

@bot.message_handler(func=lambda message: True)
def play_game(message):
    chat_id = message.chat.id
    
    # Agar foydalanuvchi /play bosmasdan to'g'ridan-to'g'ri yozsa
    if chat_id not in user_games:
        bot.reply_to(message, "❌ Siz hali o'yin boshlamadingiz. Yangi o'yin uchun /play buyrug'ini bering.")
        return
        
    bot.send_chat_action(chat_id, 'typing')
    user_text = message.text
    
    # Tarixni olamiz va yangi savolni qo'shamiz
    chat_history = user_games[chat_id]["history"]
    chat_history.append({"role": "user", "parts": [user_text]})
    
    try:
        # AI butun o'yin tarixini ko'rib, xarakterdan chiqmasdan javob beradi
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=chat_history, # Bu yerda faqat bitta matn emas, butun suhbat tarixi ketadi
        )
        
        # AI javobini ham tarixga qo'shamiz
        chat_history.append({"role": "model", "parts": [response.text]})
        
        bot.reply_to(message, response.text)
        
    except Exception as e:
        bot.reply_to(message, "AI javob berishda biroz o'ylanib qoldi. Qaytadan yozib ko'ring.")

# Railway Webhook qismlari
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
        return "O'yin bot webhooki yoqildi!", 200
    return "URL topilmadi!", 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
