import os
import time
import logging
import telebot
from src.database.db_manager import DatabaseManager
from src.models.subscription import Subscription

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TelegramBot")

# 1. Configuration
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TOKEN_HERE")
# Personal Admin ID in a minute so you can receive bug reports!
ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_ID", "") 

bot = telebot.TeleBot(BOT_TOKEN)
db = DatabaseManager()

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    text = (
        "⚡ *Dobrodošli u BiH Power Alerts!*\n\n"
        "Prijavite se za obavijesti o nestanku struje. Komande:\n\n"
        "📝 `/subscribe ulica, broj, grad`\n"
        "*(Primjer: /subscribe Kračule, 12, Sarajevo)*\n\n"
        "🏡 *Ako ste na selu ili drugom mjestu bez broja:*\n"
        "*(Primjer: /subscribe Donja Koprivna, , Cazin)*\n\n"
        "🐞 `/report [vaša poruka]` - Prijavite grešku\n"
        "🆔 `/myid` - Prikazuje vaš sistemski ID"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['myid'])
def show_id(message):
    bot.reply_to(message, f"Vaš Telegram Chat ID je: `{message.chat.id}`", parse_mode="Markdown")

@bot.message_handler(commands=['report'])
def handle_report(message):
    if not ADMIN_CHAT_ID:
        bot.reply_to(message, "Sistem za prijave trenutno nije konfigurisan.")
        return
        
    # Extract the message after the command
    report_text = message.text.replace("/report", "").strip()
    if not report_text:
        bot.reply_to(message, "Napišite poruku nakon komande. Primjer: `/report Nisam dobio alert!`", parse_mode="Markdown")
        return

    # Forward securely to the Admin
    admin_msg = f"🚨 *NOVI BUG REPORT*\nOd: {message.from_user.first_name} (ID: `{message.chat.id}`)\nPoruka: {report_text}"
    try:
        bot.send_message(ADMIN_CHAT_ID, admin_msg, parse_mode="Markdown")
        bot.reply_to(message, "✅ Vaša prijava je uspješno poslana developeru. Hvala!")
    except Exception as e:
        logger.error(f"Failed to send report to admin: {e}")
        bot.reply_to(message, "Došlo je do greške pri slanju prijave.")

@bot.message_handler(commands=['subscribe'])
def handle_subscribe(message):
    # Strip the command part
    raw_data = message.text.replace("/subscribe", "").strip()
    
    # Expecting format: Street, House, City
    parts = [p.strip() for p in raw_data.split(",")]
    
    if len(parts) != 3:
        bot.reply_to(message, "❌ Pogrešan format!\nIspravno: `/subscribe Ulica, Broj, Grad`\nAko nemate broj: `/subscribe Selo, , Grad`", parse_mode="Markdown")
        return
        
    street_name, house_number, municipality = parts
    chat_id_string = f"telegram:{message.chat.id}"
    
    # Create the Subscription Object
    new_sub = Subscription(
        street_name=street_name,
        municipality=municipality,
        house_number=house_number,
        push_endpoint=chat_id_string,  # We use a 'telegram:' prefix so the notifier knows where to route this!
        push_keys={},
        is_rural=(house_number == ""), # Auto-detect rural if number is blank
        provider_preference=["EPBiH", "Elektrokrajina", "EPHZHB", "Elektro Bijeljina", "Elektro Doboj"] # Default all
    )
    
    # Save to Database
    success = db.save_subscription(new_sub)
    
    if success:
        bot.reply_to(message, f"✅ Uspješno ste prijavljeni!\n📍 Lokacija: {street_name} {house_number}, {municipality}\nDobijat ćete poruku čim se najavi nestanak struje.")
    else:
        bot.reply_to(message, "Sistem je prijavio grešku ili ste već prijavljeni sa ovom adresom.")

def main():
    logger.info("Starting Telegram Long-Polling Bot...")
    # Long polling loop with aggressive exception handling so it never crashes
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            logger.error(f"Telegram polling crashed: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
