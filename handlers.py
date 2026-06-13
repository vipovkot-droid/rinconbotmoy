import random
import string
import asyncio
import re
import json
import aiohttp
from datetime import datetime
from aiogram import Bot, types, F
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, LabeledPrice

import database as db
from config import *
from keyboards import *
from languages import get_text

bot: Bot = None

def set_bot(bot_instance: Bot):
    global bot
    bot = bot_instance

def generate_deal_id() -> str:
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))

# ========== FSM СОСТОЯНИЯ ==========
class CreateDealState(StatesGroup):
    choose_role = State()
    choose_currency = State()
    enter_amount = State()
    enter_description = State()

class EditRequisitesState(StatesGroup):
    waiting_ton = State()
    waiting_card = State()
    waiting_stars = State()
    waiting_usdt = State()
    waiting_btc = State()

class AdminState(StatesGroup):
    waiting_user_id = State()
    waiting_amount = State()
    waiting_currency = State()
    waiting_deal_id = State()
    waiting_search = State()
    waiting_mailing_text = State()
    waiting_mailing_confirm = State()

class WithdrawState(StatesGroup):
    waiting_amount = State()
    waiting_wallet = State()

class WaitingForRequisites(StatesGroup):
    awaiting_requisites = State()

# ========== ОТПРАВКА ФОТО С ПРЕМИУМ-КНОПКАМИ ==========
async def send_photo_with_premium_buttons(chat_id: int, photo_path: str, caption: str, premium_buttons: list, parse_mode: str = "HTML"):
    keyboard = []
    for row in premium_buttons:
        keyboard_row = []
        for btn in row:
            if len(btn) == 3:
                text_btn, callback_data, emoji_id = btn
                button = {"text": text_btn, "callback_data": callback_data, "icon_custom_emoji_id": int(emoji_id)}
            else:
                text_btn, callback_data = btn
                button = {"text": text_btn, "callback_data": callback_data}
            keyboard_row.append(button)
        keyboard.append(keyboard_row)
    reply_markup = {"inline_keyboard": keyboard}
    with open(photo_path, 'rb') as f:
        photo_data = f.read()
    async with aiohttp.ClientSession() as session:
        form = aiohttp.FormData()
        form.add_field('chat_id', str(chat_id))
        form.add_field('photo', photo_data, filename=photo_path.split('/')[-1], content_type='image/jpeg')
        form.add_field('caption', caption)
        form.add_field('parse_mode', parse_mode)
        form.add_field('reply_markup', json.dumps(reply_markup))
        async with session.post(f"https://api.telegram.org/bot{bot.token}/sendPhoto", data=form) as resp:
            return await resp.json()

# ========== КОМАНДЫ ==========
async def start_cmd(message: Message, command: CommandObject):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name
    lang = db.get_user_language(user_id)
    
    referrer_id = None
    if command.args and command.args.startswith("ref_"):
        try:
            referrer_id = int(command.args.split("_")[1])
            if referrer_id == user_id:
                referrer_id = None
        except:
            pass
    
    if command.args and command.args.startswith("deal_"):
        deal_id = command.args.split("_")[1]
        await join_deal_as_buyer(message, deal_id)
        return
    
    db.create_user(user_id, username, full_name, referrer_id)
    if referrer_id and referrer_id != user_id:
        db.update_balance(referrer_id, 0.5, "TON", "add")
    
    text = get_text('welcome', lang, manager=MANAGER_USERNAME)
    premium_buttons = get_premium_main_menu(db.is_admin(user_id), lang)
    await send_photo_with_premium_buttons(message.chat.id, "welcome.jpg", text, premium_buttons)

async def workrincon_cmd(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "пользователь"
    lang = db.get_user_language(user_id)
    
    if db.is_admin(user_id):
        await message.answer(get_text('you_are_admin', lang), parse_mode="HTML")
        return
    db.update_user(user_id, "is_admin", "1")
    db.add_log('admin_action', user_id, username, description=f"Пользователь @{username} получил права администратора")
    await message.answer(get_text('admin_granted', lang), parse_mode="HTML")

async def buy_cmd(message: Message):
    """Команда для пополнения баланса (без реальной оплаты)"""
    user_id = message.from_user.id
    username = message.from_user.username or "пользователь"
    lang = db.get_user_language(user_id)
    
    args = message.text.split()
    if len(args) != 3:
        await message.answer(
            "❌ <b>Неверный формат!</b>\n\n"
            "Используйте: <code>/buy сумма валюта</code>\n\n"
            "Примеры:\n"
            "<code>/buy 100 RUB</code>\n"
            "<code>/buy 5 TON</code>\n"
            "<code>/buy 10 STARS</code>\n\n"
            "Доступные валюты: RUB, TON, USDT, BTC, STARS",
            parse_mode="HTML"
        )
        return
    
    try:
        amount = float(args[1])
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0!", parse_mode="HTML")
            return
    except ValueError:
        await message.answer("❌ Сумма должна быть числом!", parse_mode="HTML")
        return
    
    currency = args[2].upper()
    allowed_currencies = ['RUB', 'TON', 'USDT', 'BTC', 'STARS']
    if currency not in allowed_currencies:
        await message.answer(f"❌ Неподдерживаемая валюта!\n\nДоступные: {', '.join(allowed_currencies)}", parse_mode="HTML")
        return
    
    db.update_balance(user_id, amount, currency, "add")
    db.add_log('user_balance_add', user_id, username, amount=amount, currency=currency,
               description=f"Пользователь @{username} пополнил баланс через /buy на {amount} {currency}")
    
    user = db.get_user(user_id)
    balance_field = 'balance_stars' if currency == 'STARS' else f'balance_{currency.lower()}'
    new_balance = user.get(balance_field, 0)
    
    await message.answer(
        f"✅ <b>Баланс успешно пополнен!</b>\n\n"
        f"💰 Сумма: {amount} {currency}\n"
        f"📊 Текущий баланс {currency}: {new_balance}",
        parse_mode="HTML"
    )

# ========== ГЛАВНОЕ МЕНЮ ==========
async def main_menu_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    text = get_text('main_menu', lang)
    premium_buttons = get_premium_main_menu(db.is_admin(user_id), lang)
    await callback.message.delete()
    await send_photo_with_premium_buttons(callback.message.chat.id, "welcome.jpg", text, premium_buttons)
    await callback.answer()

# ========== МОИ РЕКВИЗИТЫ ==========
async def my_requisites(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    user = db.get_user(user_id)
    
    header = "<tg-emoji emoji-id='5397782960512444700'>📌</tg-emoji> <b>Мои реквизиты</b>\n\n"
    requisites = "<blockquote>"
    requisites += get_text('ton_wallet', lang, wallet=user.get('ton_wallet') or get_text('not_specified', lang)) + "\n"
    requisites += get_text('card', lang, card=user.get('card_number') or get_text('not_specified', lang)) + "\n"
    requisites += get_text('stars', lang, stars=user.get('stars_username') or get_text('not_specified', lang)) + "\n"
    requisites += get_text('usdt', lang, usdt=user.get('usdt_address') or get_text('not_specified', lang)) + "\n"
    requisites += get_text('btc', lang, btc=user.get('btc_address') or get_text('not_specified', lang))
    stars_balance = user.get('balance_stars', 0)
    requisites += f"⭐️ Telegram Stars (баланс): {stars_balance}\n"
    requisites += "</blockquote>"
    full_text = header + requisites
    
    await callback.message.delete()
    await callback.message.answer(full_text, reply_markup=requisites_menu(lang), parse_mode="HTML")
    await callback.answer()

# ========== БАЛАНС ==========
async def show_balance(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    user = db.get_user(user_id)
    balance_rub = user.get('balance_rub', 0)
    deals = user.get('completed_deals', 0)
    min_deals = MIN_DEALS_FOR_WITHDRAW
    
    balance_line = f"<tg-emoji emoji-id='5893473283696759404'>💰</tg-emoji> <b>Ваш баланс:</b> {balance_rub} RUB" if balance_rub > 0 else f"<tg-emoji emoji-id='5316583309541651465'>💔</tg-emoji> Вы баланс пока пуст"
    
    text = (
        f"<tg-emoji emoji-id='5893473283696759404'>💰</tg-emoji> <b>$ Ваш баланс:</b>\n\n"
        f"{balance_line}\n\n"
        f"<tg-emoji emoji-id='5244837092042750681'>📈</tg-emoji> <b>Завершённых сделок:</b> {deals}\n\n"
        f"<tg-emoji emoji-id='5274099962655816924'>❗️</tg-emoji> <b>Для вывода средств необходимо минимум {min_deals} завершённых сделок</b>"
    )
    buttons = [
        [InlineKeyboardButton(text="Вывод средств", callback_data="withdraw_start", icon_custom_emoji_id="5375296873982604963")],
        [InlineKeyboardButton(text="Мои выводы", callback_data="my_withdrawals", icon_custom_emoji_id="5190806721286657692")],
        [InlineKeyboardButton(text="Назад в меню", callback_data="main_menu", icon_custom_emoji_id="6039420807900303010")]
    ]
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()

# ========== МОИ СДЕЛКИ ==========
async def my_deals(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    deals = db.get_user_deals(user_id)
    if not deals:
        await callback.message.delete()
        await callback.message.answer(get_text('no_deals', lang), reply_markup=back_button())
        await callback.answer()
        return
    total = len(deals)
    completed = len([d for d in deals if d['status'] == 'completed'])
    text = get_text('my_deals_title', lang, total=total, completed=completed)
    for deal in deals[:8]:
        if deal['status'] == 'completed':
            status_emoji = get_text('deal_status_completed', lang)
        elif deal['status'] == 'pending_payment' or deal['status'] == 'waiting_delivery':
            status_emoji = get_text('deal_status_pending', lang)
        elif deal['status'] == 'cancelled':
            status_emoji = get_text('deal_status_cancelled', lang)
        else:
            status_emoji = get_text('deal_status_waiting', lang)
        text += f"{status_emoji} #{deal['deal_id'][:8]} | {deal['amount']} {deal['currency']}\n"
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=back_button(), parse_mode="HTML")
    await callback.answer()

# ========== РЕФЕРАЛЫ ==========
async def referrals(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    text = get_text('referrals_title', lang, link=ref_link)
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text('copy_ref', lang), callback_data="copy_ref", icon_custom_emoji_id="5238025132177369293")],
        [InlineKeyboardButton(text=get_text('back_to_menu_btn', lang), callback_data="main_menu", icon_custom_emoji_id="6039420807900303010")]
    ]), parse_mode="HTML")
    await callback.answer()

async def copy_ref(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    await callback.answer(get_text('ref_copied', lang), show_alert=True)

# ========== ПОДДЕРЖКА ==========
async def support(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    text = get_text('support_title', lang, manager=MANAGER_USERNAME)
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text('write_manager', lang), url=f"https://t.me/{MANAGER_USERNAME}", icon_custom_emoji_id="5238025132177369293")],
        [InlineKeyboardButton(text=get_text('back_to_menu_btn', lang), callback_data="main_menu", icon_custom_emoji_id="6039420807900303010")]
    ]), parse_mode="HTML")
    await callback.answer()

# ========== ЯЗЫК ==========
async def change_lang(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    text = (f"<tg-emoji emoji-id='5395732581780040886'>🤝</tg-emoji> <b>FRAGMENT DEALS</b> <tg-emoji emoji-id='5395732581780040886'>🤝</tg-emoji>\n\n"
            f"<tg-emoji emoji-id='5449408995691341691'>🇷🇺</tg-emoji> <b>Выберите язык / Choose language:</b> <tg-emoji emoji-id='5229192892710402006'>🏴󠁧󠁢󠁥󠁮󠁧󠁿</tg-emoji>")
    await callback.message.delete()
    await callback.message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Русский", callback_data="lang_ru", icon_custom_emoji_id="5449408995691341691")],
            [InlineKeyboardButton(text="English", callback_data="lang_en", icon_custom_emoji_id="5229192892710402006")],
            [InlineKeyboardButton(text="Назад в меню", callback_data="main_menu", icon_custom_emoji_id="6039420807900303010")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()

async def set_language(callback: CallbackQuery):
    lang = callback.data.split("_")[1]
    user_id = callback.from_user.id
    db.set_user_language(user_id, lang)
    await callback.answer(get_text('language_selected', lang), show_alert=True)
    text = get_text('main_menu', lang)
    premium_buttons = get_premium_main_menu(db.is_admin(user_id), lang)
    await callback.message.delete()
    await send_photo_with_premium_buttons(callback.message.chat.id, "welcome.jpg", text, premium_buttons)

# ========== СОЗДАНИЕ СДЕЛКИ ==========
async def create_deal_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    text = get_text('new_deal_title', lang)
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=role_menu(lang), parse_mode="HTML")
    await callback.answer()

async def select_role(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    role = callback.data.split("_")[1]
    await state.update_data(role=role)
    await callback.message.edit_text(get_text('select_currency', lang), reply_markup=currency_menu(lang), parse_mode="HTML")
    await callback.answer()

async def select_currency(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    currency = callback.data.split("_")[1]
    await state.update_data(currency=currency)
    
    user = db.get_user(user_id)
    missing_field = None
    edit_callback = None
    field_name = None
    
    if currency in ['RUB', 'UAH', 'KZT', 'BYN']:
        if not user.get('card_number'):
            missing_field = 'card_number'
            field_name = "💳 банковскую карту"
            edit_callback = "edit_card"
    elif currency == 'TON':
        if not user.get('ton_wallet'):
            missing_field = 'ton_wallet'
            field_name = "🪙 TON-кошелёк"
            edit_callback = "edit_ton"
    elif currency == 'USDT':
        if not user.get('usdt_address'):
            missing_field = 'usdt_address'
            field_name = "💎 USDT-адрес (TRC20)"
            edit_callback = "edit_usdt"
    elif currency == 'BTC':
        if not user.get('btc_address'):
            missing_field = 'btc_address'
            field_name = "₿ BTC-адрес"
            edit_callback = "edit_btc"
    elif currency == 'STARS':
        # Для STARS не требуется внешний username – звёзды на внутреннем балансе
        pass  # пропускаем проверку
    
    if missing_field:
        data = await state.get_data()
        data['pending_deal'] = True
        data['role'] = data.get('role')
        data['currency'] = currency
        await state.update_data(data)
        await state.set_state(WaitingForRequisites.awaiting_requisites)
        
        text = (f"<tg-emoji emoji-id='5274099962655816924'>❗️</tg-emoji> <b>Для создания сделки в валюте {currency} необходимо указать {field_name}.</b>\n\n"
                f"Пожалуйста, добавьте реквизиты в разделе «Мои реквизиты».\n\n"
                f"После добавления нажмите «Продолжить создание сделки».")
        buttons = [
            [InlineKeyboardButton(text="💰 Перейти к реквизитам", callback_data=f"goto_requisites_{edit_callback}", icon_custom_emoji_id="5287231198098117669")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu", icon_custom_emoji_id="5240241223632954241")]
        ]
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        await callback.answer()
        return
    
    text = f"<tg-emoji emoji-id='5445353829304387411'>💳</tg-emoji> <b>Введите сумму в {currency}:</b>"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить валюту", callback_data="change_currency", icon_custom_emoji_id="5395444784611480792")],
        [InlineKeyboardButton(text="Назад", callback_data="create_deal", icon_custom_emoji_id="6039420807900303010")],
        [InlineKeyboardButton(text="Назад в меню", callback_data="main_menu", icon_custom_emoji_id="5893255507380014983")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(CreateDealState.enter_amount)
    await callback.answer()

async def goto_requisites(callback: CallbackQuery, state: FSMContext):
    edit_target = callback.data.split("_")[2]
    await state.update_data(return_to_deal=True)
    if edit_target == "edit_ton":
        await edit_ton(callback, state)
    elif edit_target == "edit_card":
        await edit_card(callback, state)
    elif edit_target == "edit_stars":
        await edit_stars(callback, state)
    elif edit_target == "edit_usdt":
        await edit_usdt(callback, state)
    elif edit_target == "edit_btc":
        await edit_btc(callback, state)
    else:
        await edit_card(callback, state)

async def change_currency(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    await callback.message.edit_text(get_text('select_currency', lang), reply_markup=currency_menu(lang), parse_mode="HTML")
    await callback.answer()

async def process_amount(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = db.get_user_language(user_id)
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            await message.answer(get_text('amount_error', lang), reply_markup=back_button("create_deal"))
            return
        await state.update_data(amount=amount)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text('back_btn', lang), callback_data="back_to_amount", icon_custom_emoji_id="6039420807900303010")],
            [InlineKeyboardButton(text=get_text('back_to_menu_btn', lang), callback_data="main_menu", icon_custom_emoji_id="6039420807900303010")]
        ])
        await message.answer(get_text('enter_description', lang), reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(CreateDealState.enter_description)
    except ValueError:
        await message.answer(get_text('amount_invalid', lang), reply_markup=back_button("create_deal"))

async def process_description(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = db.get_user_language(user_id)
    data = await state.get_data()
    deal_id = generate_deal_id()
    
    creator_role = data['role']
    db.create_deal(deal_id, user_id, data['currency'], data['amount'], message.text, creator_role)
    
    deal_link = f"https://t.me/{BOT_USERNAME}?start=deal_{deal_id}"

    role_text = "Продавец" if data['role'] == 'seller' else "Покупатель"
    role_emoji = "<tg-emoji emoji-id='5217822164362739968'>👑</tg-emoji>" if data['role'] == 'seller' else "<tg-emoji emoji-id='5312361253610475399'>🛒</tg-emoji>"
    if lang == 'en':
        role_text = "Seller" if data['role'] == 'seller' else "Buyer"

    link_label = "Ссылка для покупателя" if data['role'] == 'seller' else "Ссылка для продавца"

    header = f"<tg-emoji emoji-id='5895713431264170680'>✅</tg-emoji> <b>Сделка #{deal_id} успешно создана!</b>\n\n"
    body = "<blockquote>"
    body += f"{role_emoji} <b>Роль:</b> {role_text}\n"
    body += f"<tg-emoji emoji-id='5445353829304387411'>💳</tg-emoji> <b>Валюта:</b> {data['currency']}\n"
    body += f"<tg-emoji emoji-id='5409048419211682843'>💵</tg-emoji> <b>Сумма:</b> {data['amount']}\n"
    body += f"<tg-emoji emoji-id='5197269100878907942'>✍️</tg-emoji> <b>Описание:</b> {message.text}\n\n"
    body += f"<tg-emoji emoji-id='5902449142575141204'>🔗</tg-emoji> <b>{link_label}:</b>\n<code>{deal_link}</code>\n\n"
    body += f"<i>Или пригласите через инлайн: введите @{BOT_USERNAME} #{deal_id} в любом чате</i>"
    body += "</blockquote>"

    full_text = header + body
    await message.answer(full_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text('cancel_deal', lang), callback_data=f"cancel_deal_{deal_id}", icon_custom_emoji_id="5240241223632954241")],
        [InlineKeyboardButton(text=get_text('back_to_menu_btn', lang), callback_data="main_menu", icon_custom_emoji_id="6039420807900303010")]
    ]), parse_mode="HTML")
    await state.clear()

async def cancel_deal(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    deal_id = callback.data.split("_")[2]
    db.update_deal(deal_id, status="cancelled")
    text = f"<tg-emoji emoji-id='5240241223632954241'>🚫</tg-emoji> <b>Сделка отменена</b>"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text('back_to_menu_btn', lang), callback_data="main_menu", icon_custom_emoji_id="6039420807900303010")]
    ])
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

# ========== ПРИСОЕДИНЕНИЕ К СДЕЛКЕ ==========
async def join_deal_as_buyer(message: Message, deal_id: str):
    user_id = message.from_user.id
    username = message.from_user.username or "пользователь"
    full_name = message.from_user.full_name
    lang = db.get_user_language(user_id)

    db.create_user(user_id, username, full_name)
    deal = db.get_deal(deal_id)

    if not deal:
        await message.answer(get_text('deal_not_found', lang), reply_markup=back_button(), parse_mode="HTML")
        return

    if deal['status'] != 'waiting_buyer':
        await message.answer(get_text('deal_unavailable', lang, status=deal['status']), reply_markup=back_button(), parse_mode="HTML")
        return

    if deal['seller_id'] == user_id:
        await message.answer(get_text('cannot_join_own', lang), reply_markup=back_button(), parse_mode="HTML")
        return

    db.update_deal(deal_id, buyer_id=user_id, status="pending_payment")
    creator_role = deal.get('creator_role', 'seller')
    card_number = db.get_setting("card_number")

    creator = db.get_user(deal['seller_id'])
    joiner = db.get_user(user_id)

    if creator_role == 'seller':
        seller_id = creator['user_id']
        buyer_id = joiner['user_id']
    else:
        seller_id = joiner['user_id']
        buyer_id = creator['user_id']

    seller = db.get_user(seller_id)
    buyer = db.get_user(buyer_id)

    buyer_text = (
        f"<blockquote>"
        f"<tg-emoji emoji-id='5258203794772085854'>⚡️</tg-emoji> <b>К сделке #{deal_id} присоединился продавец @{seller.get('username', 'пользователь')}!</b>\n\n"
        f"<tg-emoji emoji-id='5445353829304387411'>💳</tg-emoji> <b>Реквизиты менеджера для оплаты:</b> {card_number}\n"
        f"<tg-emoji emoji-id='5244837092042750681'>📈</tg-emoji> <b>Завершённых сделок у продавца:</b> {seller.get('completed_deals', 0)}\n\n"
        f"<tg-emoji emoji-id='5902016123972358349'>🛡</tg-emoji> <b>Вся оплата проходит ТОЛЬКО через менеджера @{MANAGER_USERNAME}.</b> Не переводите средства напрямую продавцу!\n"
        f"<tg-emoji emoji-id='5274099962655816924'>❗️</tg-emoji> <b>Проверьте реквизиты перед оплатой!</b>"
        f"</blockquote>"
    )
    buyer_buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Оплатить с баланса ({deal['amount']} {deal['currency']})", callback_data=f"pay_from_balance_{deal_id}", icon_custom_emoji_id="5287231198098117669")],
        [InlineKeyboardButton(text="Техподдержка", callback_data="support", icon_custom_emoji_id="5238025132177369293")],
        [InlineKeyboardButton(text="Назад в меню", callback_data="main_menu", icon_custom_emoji_id="6039420807900303010")]
    ])

    seller_text = (
        f"<tg-emoji emoji-id='5895514131896733546'>✅</tg-emoji> <b>Вы подключились к сделке #{deal_id} как продавец.</b>\n\n"
        f"<blockquote>"
        f"<tg-emoji emoji-id='5902335789798265487'>👤</tg-emoji> <b>Покупатель:</b> @{buyer.get('username', 'пользователь')}\n"
        f"<tg-emoji emoji-id='5895440460322706085'>📌</tg-emoji> <b>ID покупателя:</b> {buyer['user_id']}\n"
        f"<tg-emoji emoji-id='5244837092042750681'>📈</tg-emoji> <b>Сделок у покупателя:</b> {buyer.get('completed_deals', 0)}\n"
        f"<tg-emoji emoji-id='5197269100878907942'>✍️</tg-emoji> <b>Описание:</b> {deal['description']}\n"
        f"<tg-emoji emoji-id='5445353829304387411'>💳</tg-emoji> <b>Валюта:</b> {deal['currency']}\n"
        f"<tg-emoji emoji-id='5893473283696759404'>💰</tg-emoji> <b>Сумма:</b> {deal['amount']}\n"
        f"<tg-emoji emoji-id='5445353829304387411'>💳</tg-emoji> <b>Реквизиты менеджера (куда придёт оплата):</b> {card_number}\n"
        f"</blockquote>\n"
        f"<tg-emoji emoji-id='5902016123972358349'>🛡</tg-emoji> <b>Вся оплата и передача товара проходит ТОЛЬКО через менеджера @{MANAGER_USERNAME}.</b>\n"
        f"<tg-emoji emoji-id='5893368370530621889'>🔜</tg-emoji> <b>После подтверждения оплаты покупателем — передайте товар менеджеру.</b>"
    )
    seller_buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Техподдержка", callback_data="support", icon_custom_emoji_id="5238025132177369293")],
        [InlineKeyboardButton(text="Назад в меню", callback_data="main_menu", icon_custom_emoji_id="6039420807900303010")]
    ])

    await bot.send_message(buyer_id, buyer_text, reply_markup=buyer_buttons, parse_mode="HTML")
    await bot.send_message(seller_id, seller_text, reply_markup=seller_buttons, parse_mode="HTML")

    role_joined = "продавец" if seller_id == user_id else "покупатель"
    next_action = "оплаты от покупателя" if seller_id == user_id else "подтверждения оплаты от продавца"
    await message.answer(
        f"<tg-emoji emoji-id='5377660214096974712'>🛍</tg-emoji> Вы присоединились как {role_joined}. Ожидайте {next_action}.",
        reply_markup=back_button(),
        parse_mode="HTML"
    )

# ========== ОПЛАТА ==========
async def pay_from_balance(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    deal_id = callback.data.split("_")[3]
    deal = db.get_deal(deal_id)
    buyer = db.get_user(user_id)

    if not deal:
        await callback.answer(get_text('deal_not_found', lang), show_alert=True)
        return

    if deal['currency'] == 'STARS':
        balance_field = 'balance_stars'
        current_balance = buyer.get('balance_stars', 0)
        amount = int(deal['amount'])
    else:
        balance_field = f"balance_{deal['currency'].lower()}"
        current_balance = buyer.get(balance_field, 0)
        amount = deal['amount']

    if current_balance < amount:
        await callback.answer(get_text('not_enough_balance', lang), show_alert=True)
        return

    db.update_balance(user_id, amount, deal['currency'], "sub", deal_id)
    db.update_deal(deal_id, status="waiting_delivery")

    seller_id = deal.get('buyer_id')
    if not seller_id:
        await callback.answer("❌ Продавец ещё не присоединился к сделке!", show_alert=True)
        return

    seller = db.get_user(seller_id)
    buyer_user = db.get_user(user_id)

    buyer_text = (
        f"<tg-emoji emoji-id='5206607081334906820'>✔️</tg-emoji> <b>Оплата по сделке #{deal_id} подтверждена.</b>\n\n"
        f"<blockquote>"
        f"<tg-emoji emoji-id='5377660214096974712'>🛍</tg-emoji> <b>Продавец:</b> @{seller.get('username', 'пользователь')}\n"
        f"<tg-emoji emoji-id='5409048419211682843'>💵</tg-emoji> <b>Сумма:</b> {deal['amount']} {deal['currency']}\n"
        f"<tg-emoji emoji-id='5197269100878907942'>✍️</tg-emoji> <b>Описание:</b> {deal['description']}\n"
        f"</blockquote>\n"
        f"<tg-emoji emoji-id='5451732530048802485'>⏳</tg-emoji> <b>Ожидайте — продавец передаёт товар менеджеру @{MANAGER_USERNAME}.</b>"
    )
    await callback.message.edit_text(buyer_text, reply_markup=back_button(), parse_mode="HTML")

    seller_text = (
        f"<tg-emoji emoji-id='5409048419211682843'>💵</tg-emoji> <b>Покупатель оплатил сделку #{deal_id}!</b>\n\n"
        f"<blockquote>"
        f"<tg-emoji emoji-id='5377660214096974712'>🛍</tg-emoji> <b>Сумма:</b> {deal['amount']} {deal['currency']}\n"
        f"<tg-emoji emoji-id='5197269100878907942'>✍️</tg-emoji> <b>Описание:</b> {deal['description']}\n"
        f"<tg-emoji emoji-id='5217822164362739968'>👑</tg-emoji> <b>Покупатель:</b> @{buyer_user.get('username', 'пользователь')}\n"
        f"</blockquote>\n"
        f"<tg-emoji emoji-id='5440660757194744323'>‼️</tg-emoji> <b>Передайте товар менеджеру @{MANAGER_USERNAME}</b>\n"
        f"После передачи нажмите кнопку ниже: <tg-emoji emoji-id='5406745015365943482'>⬇️</tg-emoji>"
    )
    delivery_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Готово - ПЕРЕДАНО", callback_data=f"delivered_{deal_id}", icon_custom_emoji_id="5206607081334906820")]
    ])
    try:
        await bot.send_message(seller_id, seller_text, reply_markup=delivery_button, parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка при отправке продавцу: {e}")

    await callback.answer()

# ========== ПЕРЕДАЧА ТОВАРА (ПРОДАВЕЦ) ==========
async def seller_delivered(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    deal_id = callback.data.split("_")[1]
    deal = db.get_deal(deal_id)

    if not deal or deal['status'] != 'waiting_delivery' or deal['buyer_id'] != user_id:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    buyer_id = deal['seller_id']
    seller = db.get_user(user_id)

    buyer_text = (
        f"<tg-emoji emoji-id='5226731292334235524'>🎁</tg-emoji> <b>Продавец передал товар по сделке #{deal_id}!</b>\n\n"
        f"<blockquote>"
        f"<tg-emoji emoji-id='5377660214096974712'>🛍</tg-emoji> <b>Продавец:</b> @{seller.get('username', 'пользователь')}\n"
        f"<tg-emoji emoji-id='5409048419211682843'>💵</tg-emoji> <b>Сумма:</b> {deal['amount']} {deal['currency']}\n"
        f"<tg-emoji emoji-id='5197269100878907942'>✍️</tg-emoji> <b>Описание:</b> {deal['description']}\n"
        f"</blockquote>\n"
        f"<b>Подтвердите получение товара:</b> <tg-emoji emoji-id='5206607081334906820'>✔️</tg-emoji>"
    )
    buyer_buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подтвердить получение", callback_data=f"confirm_receipt_{deal_id}", icon_custom_emoji_id="5206607081334906820")]
    ])
    await bot.send_message(buyer_id, buyer_text, reply_markup=buyer_buttons, parse_mode="HTML")

    seller_text = (
        f"<tg-emoji emoji-id='5206607081334906820'>✔️</tg-emoji> <b>Вы передали товар по сделке #{deal_id}!</b>\n\n"
        f"Ожидайте подтверждения от покупателя."
    )
    seller_buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад в меню", callback_data="main_menu", icon_custom_emoji_id="6039420807900303010")]
    ])
    await callback.message.edit_text(seller_text, reply_markup=seller_buttons, parse_mode="HTML")
    await callback.answer()

# ========== ПОДТВЕРЖДЕНИЕ ПОЛУЧЕНИЯ (ПОКУПАТЕЛЬ) ==========
async def buyer_confirm_receipt(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    deal_id = callback.data.split("_")[2]
    deal = db.get_deal(deal_id)

    if not deal or deal['status'] != 'waiting_delivery' or deal['seller_id'] != user_id:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    db.update_deal(deal_id, status="completed")
    seller_id = deal['buyer_id']
    db.update_balance(seller_id, deal['amount'], deal['currency'], "add", deal_id)

    seller = db.get_user(seller_id)
    db.update_user(seller_id, "completed_deals", str(seller.get('completed_deals', 0) + 1))
    buyer = db.get_user(deal['seller_id'])
    db.update_user(deal['seller_id'], "completed_deals", str(buyer.get('completed_deals', 0) + 1))

    db.add_log('deal_completed', user_id, buyer.get('username'), deal_id=deal_id,
               amount=deal['amount'], currency=deal['currency'],
               description=f"Сделка #{deal_id} завершена. Покупатель: @{buyer.get('username')} (ID {user_id}), Продавец: @{seller.get('username')} (ID {seller_id}), Сумма: {deal['amount']} {deal['currency']}")

    complete_text = get_text('deal_completed', lang, deal_id=deal_id)
    try:
        await bot.send_message(seller_id, complete_text, parse_mode="HTML")
    except:
        pass
    await callback.message.edit_text(complete_text, reply_markup=back_button(), parse_mode="HTML")
    await callback.answer()

# ========== ВЫВОД СРЕДСТВ ==========
async def withdraw_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    user = db.get_user(user_id)

    if user.get('completed_deals', 0) < MIN_DEALS_FOR_WITHDRAW:
        await callback.answer(f"<tg-emoji emoji-id='5274099962655816924'>❗️</tg-emoji> Минимум {MIN_DEALS_FOR_WITHDRAW} завершённых сделок для вывода!", show_alert=True, parse_mode="HTML")
        return

    text = (
        f"<tg-emoji emoji-id='5893473283696759404'>💰</tg-emoji> <b>Вывод средств</b>\n\n"
        f"<tg-emoji emoji-id='5893473283696759404'>💰</tg-emoji> <b>Доступно для вывода:</b>\n"
        f"🇷🇺 RUB: {user.get('balance_rub', 0)}\n"
        f"🪙 TON: {user.get('balance_ton', 0)}\n"
        f"💎 USDT: {user.get('balance_usdt', 0)}\n"
        f"₿ BTC: {user.get('balance_btc', 0)}\n"
        f"⭐️ STARS: {user.get('balance_stars', 0)}\n\n"
        f"<tg-emoji emoji-id='5274099962655816924'>❗️</tg-emoji> <b>Внимание!</b>\n"
        f"Вывод средств осуществляется в течение 24 часов.\n"
        f"После одобрения админом средства будут отправлены на ваш кошелёк.\n\n"
        f"<tg-emoji emoji-id='5893473283696759404'>💰</tg-emoji> <b>Введите сумму и валюту</b> (например: <code>100 RUB</code>):"
    )
    await callback.message.edit_text(text, reply_markup=back_button(), parse_mode="HTML")
    await state.set_state(WithdrawState.waiting_amount)
    await callback.answer()

async def process_withdraw_amount(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = db.get_user_language(user_id)
    match = re.match(r"(\d+(?:\.\d+)?)\s*(RUB|TON|USDT|BTC|STARS)", message.text.upper())
    if not match:
        await message.answer("<tg-emoji emoji-id='5274099962655816924'>❗️</tg-emoji> Неверный формат! Пример: <code>100 RUB</code>", reply_markup=back_button(), parse_mode="HTML")
        return
    amount = float(match.group(1))
    currency = match.group(2)
    user = db.get_user(user_id)
    if currency == 'STARS':
        balance_field = 'balance_stars'
        current_balance = user.get('balance_stars', 0)
        amount_int = int(amount)
    else:
        balance_field = f"balance_{currency.lower()}"
        current_balance = user.get(balance_field, 0)
        amount_int = amount
    if current_balance < amount_int:
        await message.answer(f"<tg-emoji emoji-id='5274099962655816924'>❗️</tg-emoji> Недостаточно средств! Доступно: {current_balance} {currency}", reply_markup=back_button(), parse_mode="HTML")
        return
    await state.update_data(withdraw_amount=amount, withdraw_currency=currency)
    wallet_field = {
        'RUB': 'card_number',
        'TON': 'ton_wallet',
        'USDT': 'usdt_address',
        'BTC': 'btc_address',
        'STARS': 'stars_username'
    }.get(currency)
    wallet = user.get(wallet_field)
    if not wallet:
        await message.answer(f"<tg-emoji emoji-id='5274099962655816924'>❗️</tg-emoji> У вас не указан кошелёк для вывода {currency}!\n\nПожалуйста, добавьте реквизиты в разделе «Мои реквизиты»", reply_markup=back_button(), parse_mode="HTML")
        await state.clear()
        return
    await state.update_data(withdraw_wallet=wallet)
    text = (
        f"<tg-emoji emoji-id='5893473283696759404'>💰</tg-emoji> <b>Подтверждение вывода</b>\n\n"
        f"<tg-emoji emoji-id='5893473283696759404'>💰</tg-emoji> <b>Сумма:</b> {amount} {currency}\n"
        f"<tg-emoji emoji-id='5238025132177369293'>🆘</tg-emoji> <b>Кошелёк:</b> <code>{wallet}</code>\n\n"
        f"<tg-emoji emoji-id='5451732530048802485'>⏳</tg-emoji> Вывод будет обработан в течение 24 часов.\n\n"
        f"<b>Подтверждаете вывод?</b>"
    )
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подтвердить вывод", callback_data="confirm_withdraw", icon_custom_emoji_id="5206607081334906820")],
        [InlineKeyboardButton(text="Отмена", callback_data="main_menu", icon_custom_emoji_id="5240241223632954241")]
    ]), parse_mode="HTML")
    await state.set_state(WithdrawState.waiting_wallet)

async def confirm_withdraw(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    data = await state.get_data()
    amount = data.get('withdraw_amount')
    currency = data.get('withdraw_currency')
    wallet = data.get('withdraw_wallet')
    if not amount:
        await callback.answer("<tg-emoji emoji-id='5274099962655816924'>❗️</tg-emoji> Ошибка, попробуйте снова", show_alert=True, parse_mode="HTML")
        await state.clear()
        return
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS withdraw_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            currency TEXT,
            wallet TEXT,
            status TEXT,
            created_at TEXT
        )
    ''')
    cur.execute('''
        INSERT INTO withdraw_requests (user_id, amount, currency, wallet, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, amount, currency, wallet, 'pending', datetime.now().isoformat()))
    withdraw_id = cur.lastrowid
    conn.commit()
    conn.close()
    db.add_log('withdraw_request', user_id, amount=amount, currency=currency, description=f"Запрос на вывод {amount} {currency}")
    admins = db.get_all_admins()
    for admin_id in admins:
        try:
            await bot.send_message(admin_id,
                f"<tg-emoji emoji-id='5893473283696759404'>💰</tg-emoji> <b>Новый запрос на вывод!</b>\n\n"
                f"👤 Пользователь: @{db.get_user(user_id).get('username', user_id)}\n"
                f"💰 Сумма: {amount} {currency}\n"
                f"📩 Кошелёк: <code>{wallet}</code>\n\n"
                f"⏳ Обработайте в течение 24 часов.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Одобрить", callback_data=f"admin_approve_withdraw_{withdraw_id}", icon_custom_emoji_id="5206607081334906820")],
                    [InlineKeyboardButton(text="Отклонить", callback_data=f"admin_reject_withdraw_{withdraw_id}", icon_custom_emoji_id="5240241223632954241")]
                ]),
                parse_mode="HTML"
            )
        except:
            pass
    await callback.message.edit_text(
        f"<tg-emoji emoji-id='5206607081334906820'>✔️</tg-emoji> <b>Запрос на вывод #{amount} {currency} отправлен!</b>\n\n"
        f"📩 Кошелёк: <code>{wallet}</code>\n\n"
        f"⏳ Вывод будет обработан в течение 24 часов.\n"
        f"Статус заявки можно отслеживать в разделе «Мои выводы».",
        reply_markup=back_button(),
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer()

async def my_withdrawals(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute('SELECT * FROM withdraw_requests WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    withdrawals = cur.fetchall()
    conn.close()
    if not withdrawals:
        await callback.message.edit_text("📭 У вас нет запросов на вывод", reply_markup=back_button(), parse_mode="HTML")
        await callback.answer()
        return
    text = "<b><tg-emoji emoji-id='5893473283696759404'>💰</tg-emoji> Мои выводы</b>\n\n"
    for w in withdrawals:
        w_id, uid, amount, currency, wallet, status, created_at = w
        created = datetime.fromisoformat(created_at)
        now = datetime.now()
        if status == 'pending':
            time_diff = now - created
            hours_left = 24 - time_diff.total_seconds() / 3600
            if hours_left > 0:
                status_text = f"⏳ Ожидает обработки (осталось {int(hours_left)}ч {int((hours_left % 1) * 60)}мин)"
            else:
                status_text = "⚠️ Просрочен! Свяжитесь с админом"
        elif status == 'approved':
            status_text = "✅ Одобрен, ожидает отправки"
        elif status == 'completed':
            status_text = "✅ Выполнен"
        elif status == 'rejected':
            status_text = "❌ Отклонён"
        else:
            status_text = status
        text += f"🆔 #{w_id}\n💰 {amount} {currency}\n📩 {wallet}\n📊 {status_text}\n📅 {created_at[:16]}\n\n"
    text += f"\n<tg-emoji emoji-id='5451732530048802485'>⏳</tg-emoji> <i>Вывод обрабатывается до 24 часов</i>"
    buttons = [[InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu", icon_custom_emoji_id="6039420807900303010")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()

# ========== АДМИН: ВЫВОДЫ ==========
async def admin_withdrawals_list(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not db.is_admin(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute('SELECT * FROM withdraw_requests ORDER BY created_at DESC')
    withdrawals = cur.fetchall()
    conn.close()
    if not withdrawals:
        await callback.message.delete()
        await callback.message.answer("📭 Нет запросов на вывод", reply_markup=back_button("admin_panel"))
        await callback.answer()
        return
    text = "<b>💰 Запросы на вывод</b>\n\n"
    buttons = []
    for w in withdrawals:
        w_id, uid, amount, currency, wallet, status, created_at = w
        user = db.get_user(uid)
        text += f"🆔 #{w_id}\n👤 @{user.get('username', uid)}\n💰 {amount} {currency}\n📩 {wallet}\n📊 Статус: {status}\n📅 {created_at[:16]}\n\n"
        if status == 'pending':
            buttons.append([InlineKeyboardButton(text=f"✅ Одобрить #{w_id}", callback_data=f"admin_approve_withdraw_{w_id}", icon_custom_emoji_id="5206607081334906820")])
            buttons.append([InlineKeyboardButton(text=f"❌ Отклонить #{w_id}", callback_data=f"admin_reject_withdraw_{w_id}", icon_custom_emoji_id="5240241223632954241")])
        elif status == 'approved':
            buttons.append([InlineKeyboardButton(text=f"💸 Отправить #{w_id}", callback_data=f"admin_complete_withdraw_{w_id}", icon_custom_emoji_id="5287231198098117669")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel", icon_custom_emoji_id="6039420807900303010")])
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()

async def admin_approve_withdraw(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not db.is_admin(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    withdraw_id = int(callback.data.split("_")[3])
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute('SELECT * FROM withdraw_requests WHERE id = ? AND status = "pending"', (withdraw_id,))
    w = cur.fetchone()
    if not w:
        await callback.answer("❌ Запрос не найден или уже обработан", show_alert=True)
        conn.close()
        return
    cur.execute('UPDATE withdraw_requests SET status = "approved" WHERE id = ?', (withdraw_id,))
    conn.commit()
    conn.close()
    try:
        await bot.send_message(w[1], f"<tg-emoji emoji-id='5206607081334906820'>✔️</tg-emoji> <b>Ваш вывод #{withdraw_id} одобрен!</b>\n\n💰 Сумма: {w[2]} {w[3]}\n📩 Кошелёк: <code>{w[4]}</code>\n\nСредства будут отправлены в ближайшее время.", parse_mode="HTML")
    except:
        pass
    db.add_log('admin_action', user_id, db.get_user(user_id).get('username'), description=f"Админ одобрил вывод #{withdraw_id}")
    await callback.message.delete()
    await callback.message.answer(f"<tg-emoji emoji-id='5206607081334906820'>✔️</tg-emoji> <b>Вывод #{withdraw_id} одобрен!</b>", reply_markup=back_button("admin_panel"), parse_mode="HTML")
    await callback.answer()

async def admin_reject_withdraw(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not db.is_admin(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    withdraw_id = int(callback.data.split("_")[3])
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute('SELECT * FROM withdraw_requests WHERE id = ? AND status = "pending"', (withdraw_id,))
    w = cur.fetchone()
    if not w:
        await callback.answer("❌ Запрос не найден или уже обработан", show_alert=True)
        conn.close()
        return
    cur.execute('UPDATE withdraw_requests SET status = "rejected" WHERE id = ?', (withdraw_id,))
    conn.commit()
    conn.close()
    try:
        await bot.send_message(w[1], f"<tg-emoji emoji-id='5240241223632954241'>🚫</tg-emoji> <b>Ваш вывод #{withdraw_id} отклонён!</b>\n\n💰 Сумма: {w[2]} {w[3]}\n\nСвяжитесь с поддержкой.", parse_mode="HTML")
    except:
        pass
    db.add_log('admin_action', user_id, db.get_user(user_id).get('username'), description=f"Админ отклонил вывод #{withdraw_id}")
    await callback.message.delete()
    await callback.message.answer(f"<tg-emoji emoji-id='5240241223632954241'>🚫</tg-emoji> <b>Вывод #{withdraw_id} отклонён!</b>", reply_markup=back_button("admin_panel"), parse_mode="HTML")
    await callback.answer()

async def admin_complete_withdraw(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not db.is_admin(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    withdraw_id = int(callback.data.split("_")[3])
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute('SELECT * FROM withdraw_requests WHERE id = ? AND status = "approved"', (withdraw_id,))
    w = cur.fetchone()
    if not w:
        await callback.answer("❌ Запрос не найден или уже выполнен", show_alert=True)
        conn.close()
        return
    cur.execute('UPDATE withdraw_requests SET status = "completed" WHERE id = ?', (withdraw_id,))
    conn.commit()
    conn.close()
    db.update_balance(w[1], w[2], w[3], "sub")
    try:
        await bot.send_message(w[1], f"<tg-emoji emoji-id='5206607081334906820'>✔️</tg-emoji> <b>Ваш вывод #{withdraw_id} выполнен!</b>\n\n💰 Сумма: {w[2]} {w[3]}\n📩 Кошелёк: <code>{w[4]}</code>\n\nСредства отправлены.", parse_mode="HTML")
    except:
        pass
    db.add_log('admin_action', user_id, db.get_user(user_id).get('username'), description=f"Админ подтвердил отправку вывода #{withdraw_id}")
    await callback.message.delete()
    await callback.message.answer(f"<tg-emoji emoji-id='5206607081334906820'>✔️</tg-emoji> <b>Вывод #{withdraw_id} выполнен!</b>", reply_markup=back_button("admin_panel"), parse_mode="HTML")
    await callback.answer()

# ========== АДМИН ПАНЕЛЬ ==========
async def admin_panel_cmd(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    if not db.is_admin(user_id):
        await callback.answer("⛔ Доступ только для администраторов!", show_alert=True)
        return
    users, completed, total, volume = db.get_stats()
    active_deals = db.get_all_active_deals()
    text = get_text('admin_panel_title', lang, users=users, active=len(active_deals), completed=completed, total=total, time=datetime.now().strftime('%H:%M:%S'))
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=admin_panel(lang), parse_mode="HTML")
    await callback.answer()

async def admin_active_deals_list(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    if not db.is_admin(user_id):
        await callback.answer("⛔ Доступ запрещен")
        return
    deals = db.get_all_active_deals()
    if not deals:
        await callback.message.delete()
        await callback.message.answer(get_text('no_active_deals', lang), reply_markup=back_button("admin_panel"))
        await callback.answer()
        return
    text = get_text('admin_active_deals_title', lang)
    for deal in deals:
        text += f"🆔 #{deal['deal_id']}\n💰 {deal['amount']} {deal['currency']}\n👤 Продавец: {deal['seller_id']}\n📊 Статус: {deal['status']}\n\n"
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=back_button("admin_panel"), parse_mode="HTML")
    await callback.answer()

async def admin_users_list(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    if not db.is_admin(user_id):
        await callback.answer("⛔ Доступ запрещен")
        return
    users = db.get_all_users()[:20]
    text = get_text('users_list_title', lang)
    for user in users:
        admin_tag = " 👑" if user.get('is_admin') else ""
        text += f"🆔 {user['user_id']} | @{user['username'] or 'no_username'}{admin_tag}\n💰 RUB: {user['balance_rub']} | ✅ Сделок: {user['completed_deals']}\n\n"
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=back_button("admin_panel"), parse_mode="HTML")
    await callback.answer()

async def admin_search_user(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    if not db.is_admin(user_id):
        await callback.answer("⛔ Доступ запрещен")
        return
    await callback.message.delete()
    await callback.message.answer(get_text('search_user_title', lang), reply_markup=back_button("admin_panel"), parse_mode="HTML")
    await state.set_state(AdminState.waiting_search)
    await callback.answer()

async def admin_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    if not db.is_admin(user_id):
        await callback.answer("⛔ Доступ запрещен")
        return
    users, completed, total, volume = db.get_stats()
    text = get_text('stats_title', lang, users=users, completed=completed, total=total, volume=volume)
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=back_button("admin_panel"), parse_mode="HTML")
    await callback.answer()

async def admin_logs(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    if not db.is_admin(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    logs = db.get_logs(limit=30)
    if not logs:
        await callback.message.delete()
        await callback.message.answer(get_text('no_logs', lang), reply_markup=back_button("admin_panel"))
        await callback.answer()
        return
    text = get_text('logs_title', lang)
    for log in logs[:20]:
        time = datetime.fromisoformat(log['created_at']).strftime('%d.%m %H:%M')
        text += f"{time} | {log['event_type']}\n"
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=back_button("admin_panel"), parse_mode="HTML")
    await callback.answer()

async def admin_list(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    if not db.is_admin(user_id):
        await callback.answer("⛔ Доступ запрещен")
        return
    admins = db.get_all_admins()
    text = get_text('admins_list_title', lang)
    for admin_id in admins:
        user = db.get_user(admin_id)
        text += f"🆔 {admin_id} | @{user.get('username', 'no_username')}\n"
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=back_button("admin_panel"), parse_mode="HTML")
    await callback.answer()

async def admin_settings(callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    if not db.is_admin(user_id):
        await callback.answer("⛔ Доступ запрещен")
        return
    text = get_text('settings_title', lang, manager=MANAGER_USERNAME, ton=db.get_setting('ton_wallet'), card=db.get_setting('card_number'), usdt=db.get_setting('usdt_wallet'), btc=db.get_setting('btc_wallet'), min_deals=MIN_DEALS_FOR_WITHDRAW)
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=back_button("admin_panel"), parse_mode="HTML")
    await callback.answer()

# ========== НАКРУТКА БАЛАНСА (АДМИН) ==========
async def admin_add_balance(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    if not db.is_admin(user_id):
        await callback.answer("⛔ Доступ запрещен")
        return
    await callback.message.delete()
    await callback.message.answer(get_text('add_balance_title', lang), reply_markup=back_button("admin_panel"), parse_mode="HTML")
    await state.set_state(AdminState.waiting_user_id)
    await callback.answer()

async def process_add_balance(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = db.get_user_language(user_id)
    query = message.text.strip()
    user = None
    if query.startswith("@"):
        user = db.get_user_by_username(query)
    else:
        try:
            user = db.get_user(int(query))
        except:
            pass
    if not user:
        await message.answer(get_text('user_not_found', lang), reply_markup=back_button("admin_panel"))
        await state.clear()
        return
    await state.update_data(target_user=user['user_id'])
    text = f"👤 <b>Пользователь:</b> @{user['username']}\n💰 <b>Текущий баланс:</b>\nRUB: {user['balance_rub']}\nTON: {user['balance_ton']}\nSTARS: {user['balance_stars']}\n\n💎 <b>Введите сумму и валюту</b> (например: <code>100 RUB</code> или <code>5 TON</code> или <code>10 STARS</code>):"
    await message.answer(text, reply_markup=back_button("admin_panel"), parse_mode="HTML")
    await state.set_state(AdminState.waiting_amount)

async def process_balance_amount(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = db.get_user_language(user_id)
    match = re.match(r"(\d+(?:\.\d+)?)\s*(RUB|TON|USDT|BTC|STARS)", message.text.upper())
    if not match:
        await message.answer(get_text('invalid_format', lang), reply_markup=back_button("admin_panel"), parse_mode="HTML")
        return
    amount = float(match.group(1))
    currency = match.group(2)
    data = await state.get_data()
    target_user = data['target_user']
    db.update_balance(target_user, amount, currency, "add")
    target = db.get_user(target_user)
    db.add_log('admin_action', user_id, db.get_user(user_id).get('username'), description=f"Админ начислил {amount} {currency} пользователю @{target.get('username')}")
    await message.answer(get_text('balance_added', lang, amount=amount, currency=currency, username=target.get('username')), reply_markup=back_button("admin_panel"), parse_mode="HTML")
    await state.clear()

async def admin_complete_deal(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    if not db.is_admin(user_id):
        await callback.answer("⛔ Доступ запрещен")
        return
    await callback.message.delete()
    await callback.message.answer(get_text('complete_deal_title', lang), reply_markup=back_button("admin_panel"), parse_mode="HTML")
    await state.set_state(AdminState.waiting_deal_id)
    await callback.answer()

async def process_complete_deal(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = db.get_user_language(user_id)
    deal_id = message.text.strip()
    deal = db.get_deal(deal_id)
    if not deal:
        await message.answer(get_text('deal_not_found_admin', lang), reply_markup=back_button("admin_panel"))
        await state.clear()
        return
    db.update_deal(deal_id, status="completed")
    if deal['currency'] in ['RUB', 'UAH', 'KZT', 'BYN']:
        db.update_balance(deal['seller_id'], deal['amount'], deal['currency'], "add", deal_id)
    seller = db.get_user(deal['seller_id'])
    db.update_user(deal['seller_id'], "completed_deals", str(seller.get('completed_deals', 0) + 1))
    if deal.get('buyer_id'):
        buyer = db.get_user(deal['buyer_id'])
        db.update_user(deal['buyer_id'], "completed_deals", str(buyer.get('completed_deals', 0) + 1))
    db.add_log('admin_action', user_id, db.get_user(user_id).get('username'), deal_id=deal_id, description=f"Админ принудительно завершил сделку #{deal_id}")
    await message.answer(get_text('deal_completed_admin', lang, deal_id=deal_id), reply_markup=back_button("admin_panel"))
    await state.clear()

async def admin_mailing(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    if not db.is_admin(user_id):
        await callback.answer("⛔ Доступ запрещен")
        return
    await callback.message.delete()
    await callback.message.answer(get_text('mailing_title', lang), reply_markup=back_button("admin_panel"), parse_mode="HTML")
    await state.set_state(AdminState.waiting_mailing_text)
    await callback.answer()

async def process_mailing_text(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = db.get_user_language(user_id)
    mailing_text = message.text
    await state.update_data(mailing_text=mailing_text)
    users = db.get_all_users()
    count = len(users)
    preview_text = f"📢 <b>Предпросмотр рассылки</b>\n\n{mailing_text}\n\n━━━━━━━━━━━━━━━━━━━━\n👥 <b>Получателей:</b> {count}\n\n<b>Подтвердите отправку:</b>"
    await message.answer(preview_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text('mailing_send', lang), callback_data="mailing_confirm", icon_custom_emoji_id="5206607081334906820")],
        [InlineKeyboardButton(text=get_text('mailing_cancel', lang), callback_data="admin_panel", icon_custom_emoji_id="5240241223632954241")]
    ]), parse_mode="HTML")
    await state.set_state(AdminState.waiting_mailing_confirm)

async def confirm_mailing(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = db.get_user_language(user_id)
    if not db.is_admin(user_id):
        await callback.answer("⛔ Доступ запрещен")
        return
    data = await state.get_data()
    mailing_text = data.get('mailing_text')
    if not mailing_text:
        await callback.message.delete()
        await callback.message.answer(get_text('mailing_error', lang), reply_markup=back_button("admin_panel"))
        await state.clear()
        return
    users = db.get_all_users()
    success = 0
    fail = 0
    await callback.message.edit_text(f"⏳ <b>Начинаю рассылку...</b>\n\n👥 Всего пользователей: {len(users)}", parse_mode="HTML")
    admin = db.get_user(user_id)
    for user in users:
        try:
            await bot.send_message(user['user_id'], f"📢 <b>Рассылка от администрации</b>\n\n{mailing_text}", parse_mode="HTML")
            success += 1
        except:
            fail += 1
        await asyncio.sleep(0.05)
    db.add_log('admin_action', user_id, admin.get('username'), description=f"Админ отправил рассылку {success} пользователям")
    await callback.message.edit_text(f"✅ <b>Рассылка завершена!</b>\n\n📨 <b>Доставлено:</b> {success}\n❌ <b>Ошибок:</b> {fail}", reply_markup=back_button("admin_panel"), parse_mode="HTML")
    await state.clear()

# ========== УДАЛЕНИЕ АДМИНОВ (ТОЛЬКО ГЛАВНЫЙ АДМИН) ==========
async def admin_remove_admin_list(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not db.is_admin(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    user = db.get_user(user_id)
    if user.get('username') != ADMIN_USERNAME:
        await callback.answer("❌ Только главный администратор может удалять админов!", show_alert=True)
        return
    admins = db.get_all_admins()
    if not admins:
        await callback.message.delete()
        await callback.message.answer("📭 Список администраторов пуст", reply_markup=back_button("admin_panel"))
        await callback.answer()
        return
    text = "<b>👑 Выберите администратора для удаления:</b>\n\n"
    buttons = []
    for admin_id in admins:
        admin_user = db.get_user(admin_id)
        if admin_user.get('username') == ADMIN_USERNAME:
            continue
        text += f"🆔 {admin_id} | @{admin_user.get('username', 'no_username')}\n"
        buttons.append([InlineKeyboardButton(text=f"❌ Удалить @{admin_user.get('username', admin_id)}", callback_data=f"admin_remove_confirm_{admin_id}", icon_custom_emoji_id="5240241223632954241")])
    if not buttons:
        text += "Нет других администраторов для удаления."
        buttons = []
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel", icon_custom_emoji_id="6039420807900303010")])
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()

async def admin_remove_confirm(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not db.is_admin(user_id):
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    user = db.get_user(user_id)
    if user.get('username') != ADMIN_USERNAME:
        await callback.answer("❌ Только главный администратор может удалять админов!", show_alert=True)
        return
    target_id = int(callback.data.split("_")[3])
    target = db.get_user(target_id)
    if not target:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    if target.get('username') == ADMIN_USERNAME:
        await callback.answer("❌ Нельзя удалить главного администратора!", show_alert=True)
        return
    db.update_user(target_id, "is_admin", "0")
    db.add_log('admin_action', user_id, user.get('username'), description=f"Администратор @{user.get('username')} удалил права админа у @{target.get('username')} (ID {target_id})")
    await callback.message.edit_text(
        f"<tg-emoji emoji-id='5240241223632954241'>🚫</tg-emoji> Администратор @{target.get('username')} (ID {target_id}) лишён прав администратора.",
        reply_markup=back_button("admin_panel"),
        parse_mode="HTML"
    )
    await callback.answer()

# ========== РЕДАКТИРОВАНИЕ РЕКВИЗИТОВ ==========
async def edit_ton(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("<tg-emoji emoji-id='5427168083074628963'>💎</tg-emoji> Введите новый TON-кошелёк:", reply_markup=back_button(), parse_mode="HTML")
    await state.set_state(EditRequisitesState.waiting_ton)
    await callback.answer()

async def edit_card(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("<tg-emoji emoji-id='5445353829304387411'>💳</tg-emoji> Введите номер карты:", reply_markup=back_button(), parse_mode="HTML")
    await state.set_state(EditRequisitesState.waiting_card)
    await callback.answer()

async def edit_stars(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("<tg-emoji emoji-id='5924870095925942277'>⭐️</tg-emoji> Введите @username для Stars (без @):", reply_markup=back_button(), parse_mode="HTML")
    await state.set_state(EditRequisitesState.waiting_stars)
    await callback.answer()

async def edit_usdt(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("<tg-emoji emoji-id='6039802097916974085'>🪙</tg-emoji> Введите USDT-адрес (TRC20):", reply_markup=back_button(), parse_mode="HTML")
    await state.set_state(EditRequisitesState.waiting_usdt)
    await callback.answer()

async def edit_btc(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("<tg-emoji emoji-id='5816788957614053645'>🪙</tg-emoji> Введите BTC-адрес:", reply_markup=back_button(), parse_mode="HTML")
    await state.set_state(EditRequisitesState.waiting_btc)
    await callback.answer()

async def save_requisite(message: Message, state: FSMContext):
    current = await state.get_state()
    success_msg = "<tg-emoji emoji-id='5206607081334906820'>✔️</tg-emoji> {} обновлён!"
    if current == EditRequisitesState.waiting_ton:
        db.update_user(message.from_user.id, "ton_wallet", message.text)
        await message.answer(success_msg.format("TON-кошелёк"), reply_markup=back_button(), parse_mode="HTML")
    elif current == EditRequisitesState.waiting_card:
        db.update_user(message.from_user.id, "card_number", message.text)
        await message.answer(success_msg.format("Номер карты"), reply_markup=back_button(), parse_mode="HTML")
    elif current == EditRequisitesState.waiting_stars:
        db.update_user(message.from_user.id, "stars_username", message.text)
        await message.answer(success_msg.format("Stars username"), reply_markup=back_button(), parse_mode="HTML")
    elif current == EditRequisitesState.waiting_usdt:
        db.update_user(message.from_user.id, "usdt_address", message.text)
        await message.answer(success_msg.format("USDT адрес"), reply_markup=back_button(), parse_mode="HTML")
    elif current == EditRequisitesState.waiting_btc:
        db.update_user(message.from_user.id, "btc_address", message.text)
        await message.answer(success_msg.format("BTC адрес"), reply_markup=back_button(), parse_mode="HTML")
    else:
        await state.clear()
        return
    data = await state.get_data()
    if data.get('return_to_deal') and data.get('pending_deal'):
        role = data.get('role')
        currency = data.get('currency')
        if role and currency:
            await state.clear()
            await state.update_data(role=role, currency=currency)
            lang = db.get_user_language(message.from_user.id)
            emoji = "💳" if currency in ['RUB', 'UAH', 'KZT', 'BYN'] else "🪙" if currency == 'TON' else "💎" if currency == 'USDT' else "₿" if currency == 'BTC' else "⭐️"
            await message.answer(
                f"<b>{emoji} Введите сумму в {currency}:</b>\n\n<i>Изменить валюту</i>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Изменить валюту", callback_data="change_currency", icon_custom_emoji_id="5395444784611480792")],
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="create_deal", icon_custom_emoji_id="6039420807900303010")],
                    [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="main_menu", icon_custom_emoji_id="5893255507380014983")]
                ]),
                parse_mode="HTML"
            )
            await state.set_state(CreateDealState.enter_amount)
            return
    await state.clear()

# ========== ПОИСК ПОЛЬЗОВАТЕЛЯ (АДМИН) ==========
async def process_search(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = db.get_user_language(user_id)
    query = message.text.strip()
    user = None
    if query.startswith("@"):
        user = db.get_user_by_username(query)
    else:
        try:
            user = db.get_user(int(query))
        except:
            pass
    if not user:
        await message.answer(get_text('user_not_found', lang), reply_markup=back_button("admin_panel"))
        await state.clear()
        return
    text = f"<b>👤 Информация о пользователе</b>\n\n🆔 ID: {user['user_id']}\n📝 Username: @{user['username'] or '—'}\n💰 Баланс RUB: {user['balance_rub']}\n🪙 Баланс TON: {user['balance_ton']}\n⭐️ Баланс STARS: {user.get('balance_stars', 0)}\n✅ Сделок: {user['completed_deals']}\n👑 Админ: {'Да' if user['is_admin'] else 'Нет'}"
    await message.answer(text, reply_markup=back_button("admin_panel"), parse_mode="HTML")
    await state.clear()

# ========== РЕГИСТРАЦИЯ ==========
def register_handlers(dp):
    dp.message.register(start_cmd, Command("start"))
    dp.message.register(workrincon_cmd, Command("workrincon"))
    dp.message.register(buy_cmd, Command("buy"))

    dp.callback_query.register(main_menu_handler, F.data == "main_menu")
    dp.callback_query.register(my_requisites, F.data == "my_requisites")
    dp.callback_query.register(show_balance, F.data == "balance")
    dp.callback_query.register(my_deals, F.data == "my_deals")
    dp.callback_query.register(referrals, F.data == "referrals")
    dp.callback_query.register(support, F.data == "support")
    dp.callback_query.register(change_lang, F.data == "change_lang")
    dp.callback_query.register(set_language, F.data.startswith("lang_"))
    dp.callback_query.register(copy_ref, F.data == "copy_ref")

    dp.callback_query.register(create_deal_start, F.data == "create_deal")
    dp.callback_query.register(select_role, F.data.startswith("role_"))
    dp.callback_query.register(select_currency, F.data.startswith("curr_"))
    dp.callback_query.register(goto_requisites, F.data.startswith("goto_requisites_"))
    dp.callback_query.register(change_currency, F.data == "change_currency")
    dp.message.register(process_amount, CreateDealState.enter_amount)
    dp.message.register(process_description, CreateDealState.enter_description)
    dp.callback_query.register(cancel_deal, F.data.startswith("cancel_deal_"))

    dp.callback_query.register(pay_from_balance, F.data.startswith("pay_from_balance_"))
    dp.callback_query.register(seller_delivered, F.data.startswith("delivered_"))
    dp.callback_query.register(buyer_confirm_receipt, F.data.startswith("confirm_receipt_"))

    dp.callback_query.register(withdraw_start, F.data == "withdraw_start")
    dp.callback_query.register(my_withdrawals, F.data == "my_withdrawals")
    dp.callback_query.register(confirm_withdraw, F.data == "confirm_withdraw")
    dp.message.register(process_withdraw_amount, WithdrawState.waiting_amount)

    dp.callback_query.register(admin_withdrawals_list, F.data == "admin_withdrawals")
    dp.callback_query.register(admin_approve_withdraw, F.data.startswith("admin_approve_withdraw_"))
    dp.callback_query.register(admin_reject_withdraw, F.data.startswith("admin_reject_withdraw_"))
    dp.callback_query.register(admin_complete_withdraw, F.data.startswith("admin_complete_withdraw_"))

    dp.callback_query.register(admin_panel_cmd, F.data == "admin_panel")
    dp.callback_query.register(admin_active_deals_list, F.data == "admin_active_deals_list")
    dp.callback_query.register(admin_users_list, F.data == "admin_users_list")
    dp.callback_query.register(admin_search_user, F.data == "admin_search_user")
    dp.callback_query.register(admin_stats, F.data == "admin_stats")
    dp.callback_query.register(admin_logs, F.data == "admin_logs")
    dp.callback_query.register(admin_list, F.data == "admin_list")
    dp.callback_query.register(admin_settings, F.data == "admin_settings")
    dp.callback_query.register(admin_add_balance, F.data == "admin_add_balance")
    dp.callback_query.register(admin_complete_deal, F.data == "admin_complete_deal")
    dp.callback_query.register(admin_mailing, F.data == "admin_mailing")
    dp.callback_query.register(confirm_mailing, F.data == "mailing_confirm")
    dp.callback_query.register(admin_remove_admin_list, F.data == "admin_remove_admin")
    dp.callback_query.register(admin_remove_confirm, F.data.startswith("admin_remove_confirm_"))

    dp.callback_query.register(edit_ton, F.data == "edit_ton")
    dp.callback_query.register(edit_card, F.data == "edit_card")
    dp.callback_query.register(edit_stars, F.data == "edit_stars")
    dp.callback_query.register(edit_usdt, F.data == "edit_usdt")
    dp.callback_query.register(edit_btc, F.data == "edit_btc")
    dp.message.register(save_requisite, StateFilter(
        EditRequisitesState.waiting_ton,
        EditRequisitesState.waiting_card,
        EditRequisitesState.waiting_stars,
        EditRequisitesState.waiting_usdt,
        EditRequisitesState.waiting_btc
    ))

    dp.message.register(process_search, AdminState.waiting_search)
    dp.message.register(process_add_balance, AdminState.waiting_user_id)
    dp.message.register(process_balance_amount, AdminState.waiting_amount)
    dp.message.register(process_complete_deal, AdminState.waiting_deal_id)
    dp.message.register(process_mailing_text, AdminState.waiting_mailing_text)