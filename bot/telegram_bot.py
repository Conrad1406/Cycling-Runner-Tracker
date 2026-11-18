import telebot

BOT_TOKEN = "8743979955:AAEmm-_8Y3e7d1_HYMT_Ka5aB2286EOXtBM"
CHAT_ID = "5350180457"

print("Verbindung wird aufgebaut...")
bot = telebot.TeleBot(BOT_TOKEN)

def send_message(inhalt):
    try:
        inhalt = (
            inhalt.replace("<br>", "\n")
            .replace("<br/>", "\n")
            .replace("<br />", "\n")
        )
        bot.send_message(CHAT_ID, inhalt, parse_mode="HTML")
        print("Erfolg")
    except Exception as e:
        print(f"Fehler: {e}")