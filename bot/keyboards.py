import os

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

AMOUNT_PRESETS = [25, 50, 100, 200, 500, 1000, 2000, 5000]

CATEGORY_ICONS = {
    "Транспорт": "🚌", "Їжа": "🍔", "Комунальні": "💡", "Оренда": "🏠",
    "Розваги": "🎮", "Здоров'я": "💊", "Інше": "📦",
}


def webapp_url() -> str | None:
    url = os.getenv("WEBAPP_URL", "").rstrip("/")
    return url if url and url.startswith("https://") else None


def reply_menu() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="📊 Огляд"), KeyboardButton(text="➕ Витрата")],
        [KeyboardButton(text="💰 Дохід"), KeyboardButton(text="🚌 Транспорт")],
    ]
    wa = webapp_url()
    if wa:
        rows.append([KeyboardButton(text="📱 Відкрити додаток", web_app=WebAppInfo(url=wa))])
    rows.append([KeyboardButton(text="⚙️ Налаштування")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def main_menu() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📊 Огляд", callback_data="menu:overview"),
         InlineKeyboardButton(text="➕ Витрата", callback_data="quick:expense")],
        [InlineKeyboardButton(text="💰 Доходи", callback_data="menu:income"),
         InlineKeyboardButton(text="🚌 Транспорт", callback_data="menu:transport")],
        [InlineKeyboardButton(text="⚙️ Налаштування", callback_data="menu:settings")],
    ]
    wa = webapp_url()
    if wa:
        rows.insert(0, [InlineKeyboardButton(text="📱 Відкрити додаток", web_app=WebAppInfo(url=wa))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def overview_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️", callback_data="month:prev"),
         InlineKeyboardButton(text="▶️", callback_data="month:next")],
        [InlineKeyboardButton(text="➕ Швидка витрата", callback_data="quick:expense")],
        [InlineKeyboardButton(text="📅 Події", callback_data="overview:events")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="menu:main")],
    ])


def quick_category_keyboard(categories: list[str]) -> InlineKeyboardMarkup:
    rows, row = [], []
    for cat in categories:
        icon = CATEGORY_ICONS.get(cat, "📦")
        row.append(InlineKeyboardButton(text=f"{icon} {cat}", callback_data=f"quick:cat:{cat}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def quick_amount_keyboard(category: str) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(AMOUNT_PRESETS), 3):
        chunk = AMOUNT_PRESETS[i:i + 3]
        rows.append([
            InlineKeyboardButton(text=f"{a} ₴", callback_data=f"quick:amt:{category}:{a}")
            for a in chunk
        ])
    rows.append([
        InlineKeyboardButton(text="✏️ Своя сума", callback_data=f"quick:custom:{category}"),
        InlineKeyboardButton(text="◀️ Категорія", callback_data="quick:expense"),
    ])
    rows.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def after_save_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Ще витрату", callback_data="quick:expense")],
        [InlineKeyboardButton(text="📊 Огляд", callback_data="menu:overview"),
         InlineKeyboardButton(text="🏠 Меню", callback_data="menu:main")],
    ])


def quick_income_amount_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(AMOUNT_PRESETS), 3):
        chunk = AMOUNT_PRESETS[i:i + 3]
        rows.append([
            InlineKeyboardButton(text=f"{a} ₴", callback_data=f"quick:inc:{a}")
            for a in chunk
        ])
    rows.append([
        InlineKeyboardButton(text="✏️ Своя сума", callback_data="quick:inc:custom"),
        InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def income_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Швидкий дохід", callback_data="quick:income")],
        [InlineKeyboardButton(text="✏️ Аванс", callback_data="income:edit:advance_amount"),
         InlineKeyboardButton(text="✏️ Зарплата", callback_data="income:edit:salary_amount")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="menu:main")],
    ])


def expenses_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡ Швидко (2 кліки)", callback_data="quick:expense")],
        [InlineKeyboardButton(text="📝 Детально", callback_data="expense:add")],
        [InlineKeyboardButton(text="📋 Список", callback_data="expense:list")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="menu:main")],
    ])


def transport_menu(auto_enabled: bool) -> InlineKeyboardMarkup:
    toggle = "✅ Авто ВКЛ" if auto_enabled else "❌ Авто ВИКЛ"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle, callback_data="transport:toggle_auto")],
        [InlineKeyboardButton(text="➕ Разова поїздка", callback_data="transport:quick_trip")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="menu:main")],
    ])


def transport_quick_keyboard(one_way: float) -> InlineKeyboardMarkup:
    daily = one_way * 2
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Сьогодні ({daily:.0f} ₴)", callback_data=f"transport:quick:{daily:.0f}")],
        [InlineKeyboardButton(text="✏️ Інша сума", callback_data="transport:add_trip")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="menu:main")],
    ])


def settings_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Аванс", callback_data="settings:advance_amount"),
         InlineKeyboardButton(text="День", callback_data="settings:advance_day")],
        [InlineKeyboardButton(text="Зарплата", callback_data="settings:salary_amount"),
         InlineKeyboardButton(text="День", callback_data="settings:salary_day")],
        [InlineKeyboardButton(text="Дорога", callback_data="settings:transport_one_way"),
         InlineKeyboardButton(text="Поїздок", callback_data="settings:transport_trips_per_day")],
        [InlineKeyboardButton(text="🏠 Меню", callback_data="menu:main")],
    ])


def categories_keyboard(categories: list[str]) -> InlineKeyboardMarkup:
    rows, row = [], []
    for cat in categories:
        icon = CATEGORY_ICONS.get(cat, "📦")
        row.append(InlineKeyboardButton(text=f"{icon} {cat}", callback_data=f"cat:{cat}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def yes_no_keyboard(yes_data: str, no_data: str = "cancel") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Так", callback_data=yes_data),
         InlineKeyboardButton(text="Ні", callback_data=no_data)],
    ])


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel")],
    ])
