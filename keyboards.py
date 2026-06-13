from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from languages import get_text

# ========== ФУНКЦИЯ ДЛЯ ПРЕМИУМ-КНОПОК ГЛАВНОГО МЕНЮ (ДЛЯ ФОТО) ==========
def get_premium_main_menu(is_admin: bool, lang: str = 'ru') -> list:
    """
    Возвращает структуру для прямой отправки главного меню с анимированными эмодзи.
    Формат: [ (текст, callback_data, emoji_id), ... ]
    """
    buttons = [
        [
            ("Мои реквизиты" if lang == 'ru' else "My requisites", "my_requisites", 5902056028513505203),
            ("Создать сделку" if lang == 'ru' else "Create deal", "create_deal", 5395732581780040886)
        ],
        [
            ("Баланс" if lang == 'ru' else "Balance", "balance", 5409048419211682843),
            ("Мои сделки" if lang == 'ru' else "My deals", "my_deals", 5397782960512444700)
        ],
        [
            ("Рефералы" if lang == 'ru' else "Referrals", "referrals", 5325559344513691205),
            ("Язык / Lang" if lang == 'ru' else "Language / Lang", "change_lang", 5902432207519093015)
        ],
        [
            ("Техподдержка" if lang == 'ru' else "Support", "support", 5238025132177369293)
        ]
    ]
    if is_admin:
        buttons.append([("Админ панель" if lang == 'ru' else "Admin panel", "admin_panel")])
    return buttons

# ========== ГЛАВНОЕ МЕНЮ (ОБЫЧНОЕ) – НЕ ИСПОЛЬЗУЕТСЯ ДЛЯ ГЛАВНОГО МЕНЮ, НО ОСТАВЛЕНО ДЛЯ СОВМЕСТИМОСТИ ==========
def main_menu(is_admin: bool = False, lang: str = 'ru') -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="Мои реквизиты" if lang == 'ru' else "My requisites",
                callback_data="my_requisites",
                icon_custom_emoji_id="5902056028513505203"   # 💳 (премиум)
            ),
            InlineKeyboardButton(
                text="Создать сделку" if lang == 'ru' else "Create deal",
                callback_data="create_deal",
                icon_custom_emoji_id="5395732581780040886"   # 🤝
            )
        ],
        [
            InlineKeyboardButton(
                text="Баланс" if lang == 'ru' else "Balance",
                callback_data="balance",
                icon_custom_emoji_id="5409048419211682843"   # 💵
            ),
            InlineKeyboardButton(
                text="Мои сделки" if lang == 'ru' else "My deals",
                callback_data="my_deals",
                icon_custom_emoji_id="5397782960512444700"   # 📌
            )
        ],
        [
            InlineKeyboardButton(
                text="Рефералы" if lang == 'ru' else "Referrals",
                callback_data="referrals",
                icon_custom_emoji_id="5325559344513691205"   # 😎
            ),
            InlineKeyboardButton(
                text="Язык / Lang" if lang == 'ru' else "Language / Lang",
                callback_data="change_lang",
                icon_custom_emoji_id="5902432207519093015"   # ⚙️
            )
        ],
        [
            InlineKeyboardButton(
                text="Техподдержка" if lang == 'ru' else "Support",
                callback_data="support",
                icon_custom_emoji_id="5238025132177369293"   # 🆘
            )
        ]
    ]
    if is_admin:
        buttons.append([
            InlineKeyboardButton(
                text="Админ панель" if lang == 'ru' else "Admin panel",
                callback_data="admin_panel",
                icon_custom_emoji_id="⚙️"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ========== КНОПКА НАЗАД (ОБЫЧНАЯ) ==========
def back_button(callback: str = "main_menu", text: str = "Назад в меню") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=callback, icon_custom_emoji_id="6039420807900303010")]
    ])
# ========== МЕНЮ РЕКВИЗИТОВ (широкие кнопки, с премиум-эмодзи) ==========
def requisites_menu(lang: str = 'ru') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="TON-кошелёк",
                callback_data="edit_ton",
                icon_custom_emoji_id="5427168083074628963"   # 💎
            )
        ],
        [
            InlineKeyboardButton(
                text="@username (Stars)",
                callback_data="edit_stars",
                icon_custom_emoji_id="5897692655273383739"   # ⭐
            )
        ],
        [
            InlineKeyboardButton(
                text="USDT-кошелёк",
                callback_data="edit_usdt",
                icon_custom_emoji_id="5287231198098117669"   # 💰
            )
        ],
        [
            InlineKeyboardButton(
                text="BTC-кошелёк",
                callback_data="edit_btc",
                icon_custom_emoji_id="5829938927703691622"   # 🪙
            )
        ],
        [
            InlineKeyboardButton(
                text="Карта",
                callback_data="edit_card",
                icon_custom_emoji_id="5445353829304387411"   # 💳
            )
        ],
        [
            InlineKeyboardButton(
                text="Назад в меню",
                callback_data="main_menu",
                icon_custom_emoji_id="6039420807900303010"   # 📥
            )
        ]
    ])

# ========== АДМИН ПАНЕЛЬ ==========
def admin_panel(lang: str = 'ru') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Активные сделки" if lang == 'ru' else "📋 Active deals", callback_data="admin_active_deals_list"),
            InlineKeyboardButton(text="👥 Пользователи" if lang == 'ru' else "👥 Users", callback_data="admin_users_list")
        ],
        [
            InlineKeyboardButton(text="🔍 Поиск юзера" if lang == 'ru' else "🔍 Search user", callback_data="admin_search_user"),
            InlineKeyboardButton(text="➕ Накрутить баланс" if lang == 'ru' else "➕ Add balance", callback_data="admin_add_balance")
        ],
        [
            InlineKeyboardButton(text="✅ Завершить сделку" if lang == 'ru' else "✅ Complete deal", callback_data="admin_complete_deal"),
            InlineKeyboardButton(text="📢 Рассылка" if lang == 'ru' else "📢 Mailing", callback_data="admin_mailing")
        ],
        [
            InlineKeyboardButton(text="📊 Статистика" if lang == 'ru' else "📊 Statistics", callback_data="admin_stats"),
            InlineKeyboardButton(text="📜 Логи" if lang == 'ru' else "📜 Logs", callback_data="admin_logs")
        ],
        [
            InlineKeyboardButton(text="👑 Список админов" if lang == 'ru' else "👑 Admins list", callback_data="admin_list"),
            InlineKeyboardButton(text="👑 Удалить админа" if lang == 'ru' else "👑 Remove admin", callback_data="admin_remove_admin"),  # НОВАЯ КНОПКА
            InlineKeyboardButton(text="⚙️ Настройки" if lang == 'ru' else "⚙️ Settings", callback_data="admin_settings")
        ],
        [
            InlineKeyboardButton(text="💰 Запросы на вывод" if lang == 'ru' else "💰 Withdrawals", callback_data="admin_withdrawals"),
            InlineKeyboardButton(text="❌ Закрыть" if lang == 'ru' else "❌ Close", callback_data="main_menu")
        ]
    ])

# ========== ВЫБОР ВАЛЮТЫ ==========
def currency_menu(lang: str = 'ru') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 RUB", callback_data="curr_RUB"),
            InlineKeyboardButton(text="🇺🇦 UAH", callback_data="curr_UAH")
        ],
        [
            InlineKeyboardButton(text="🇰🇿 KZT", callback_data="curr_KZT"),
            InlineKeyboardButton(text="🇧🇾 BYN", callback_data="curr_BYN")
        ],
        [
            InlineKeyboardButton(text="🪙 TON", callback_data="curr_TON"),
            InlineKeyboardButton(text="💎 USDT", callback_data="curr_USDT")
        ],
        [
            InlineKeyboardButton(text="₿ BTC", callback_data="curr_BTC")
        ],
        [
            InlineKeyboardButton(text="◀️ " + ("Назад" if lang == 'ru' else "Back"), callback_data="create_deal")
        ]
    ])

# ========== ВЫБОР РОЛИ (СОЗДАНИЕ СДЕЛКИ) ==========
def role_menu(lang: str = 'ru') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=get_text('seller_btn', lang),
                callback_data="role_seller",
                icon_custom_emoji_id="5217822164362739968"   # 👑
            ),
            InlineKeyboardButton(
                text=get_text('buyer_btn', lang),
                callback_data="role_buyer",
                icon_custom_emoji_id="5312361253610475399"   # 🛒
            )
        ],
        [
            InlineKeyboardButton(
                text="Назад в меню" if lang == 'ru' else "Back to menu",
                callback_data="main_menu",
                icon_custom_emoji_id="6039420807900303010"   # 📥 (премиум)
            )
        ]
    ])
# ========== КНОПКИ ДЛЯ ПЕРЕДАЧИ ТОВАРА ==========
def delivery_menu(deal_id: str, lang: str = 'ru') -> InlineKeyboardMarkup:
    text = "✅ Готово - ПЕРЕДАНО" if lang == 'ru' else "✅ DONE - TRANSFERRED"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=f"delivered_{deal_id}")]
    ])

def confirm_receipt_menu(deal_id: str, lang: str = 'ru') -> InlineKeyboardMarkup:
    text = "✅ Подтвердить получение" if lang == 'ru' else "✅ Confirm receipt"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=f"confirm_receipt_{deal_id}")]
    ])