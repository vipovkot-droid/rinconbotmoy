import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "TonRincon")
MANAGER_USERNAME = os.getenv("MANAGER_USERNAME", "FragmentsHeIp")

REFERRAL_COMMISSION = 50
MIN_DEALS_FOR_WITHDRAW = 1

BOT_NAME = "FRAGMENT DEALS"
BOT_USERNAME = "FragmentsDeaIsBot"

FIAT_CURRENCIES = ["RUB", "UAH", "KZT", "BYN"]
CRYPTO_CURRENCIES = ["TON", "USDT", "BTC"]
STARS_CURRENCY = ["STARS"]

DB_PATH = "fragment_deals.db"

# ID премиум-эмодзи (можно использовать в текстах)
PREMIUM_EMOJI_ID = "5409048419211682843"  # 💵 (пример)

# ID для кнопок главного меню (главный ID)
PREMIUM_MAIN_EMOJI = {
    "requisites": "5902056028513505203",  # 💳
    "create_deal": "5395732581780040886", # 🤝
    "balance": "5409048419211682843",     # 💵
    "my_deals": "5397782960512444700",    # 📌
    "referrals": "5325559344513691205",   # 😎
    "language": "5902432207519093015",    # ⚙️
    "support": "5238025132177369293",     # 🆘
}