import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "	TonRincon")
MANAGER_USERNAME = os.getenv("MANAGER_USERNAME", "FragmentsHeIp")

REFERRAL_COMMISSION = 50
MIN_DEALS_FOR_WITHDRAW = 1

BOT_NAME = "FRAGMENT DEALS"
BOT_USERNAME = "FragmentsDeaIsBot"

FIAT_CURRENCIES = ["RUB", "UAH", "KZT", "BYN"]
CRYPTO_CURRENCIES = ["TON", "USDT", "BTC"]

DB_PATH = "fragment_deals.db"

# ДОБАВЬ ЭТУ СТРОКУ:
PREMIUM_EMOJI_ID = "5409048419211682843"