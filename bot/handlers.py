from datetime import date, datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import budget, database
from bot.budget import format_date, format_money, month_label, new_id
from bot.keyboards import (
    after_save_keyboard,
    cancel_keyboard,
    categories_keyboard,
    expenses_menu,
    income_menu,
    main_menu,
    overview_menu,
    quick_amount_keyboard,
    quick_category_keyboard,
    quick_income_amount_keyboard,
    reply_menu,
    settings_menu,
    transport_menu,
    transport_quick_keyboard,
    yes_no_keyboard,
)
from bot.states import (
    ExpenseForm,
    ExtraIncomeForm,
    MonthOverrideForm,
    QuickCustomForm,
    SettingsForm,
    TransportTripForm,
)

router = Router()

SETTINGS_LABELS = {
    "advance_amount": "Аванс (₴)", "advance_day": "День авансу (1-31)",
    "salary_amount": "Зарплата (₴)", "salary_day": "День зарплати (1-31)",
    "transport_one_way": "Вартість в один бік (₴)", "transport_trips_per_day": "Поїздок на день",
}
OVERRIDE_LABELS = {"advance_amount": "Аванс цього місяця (₴)", "salary_amount": "Зарплата цього місяця (₴)"}

REPLY_MAP = {
    "📊 Огляд": "overview",
    "➕ Витрата": "quick_expense",
    "💰 Дохід": "quick_income",
    "🚌 Транспорт": "transport",
    "⚙️ Налаштування": "settings",
}


def parse_amount(text: str) -> float | None:
    try:
        val = float(text.replace(" ", "").replace(",", ".").replace("₴", ""))
        return val if val >= 0 else None
    except ValueError:
        return None


def parse_day(text: str) -> int | None:
    try:
        d = int(text.strip())
        return d if 1 <= d <= 31 else None
    except ValueError:
        return None


def parse_date(text: str) -> str | None:
    for fmt in ("%d.%m.%Y", "%d.%m", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text.strip(), fmt)
            if fmt == "%d.%m":
                dt = dt.replace(year=date.today().year)
            return dt.date().isoformat()
        except ValueError:
            continue
    return None


async def overview_text(user_id: int) -> str:
    ctx = await budget.load_month_context(user_id)
    s = ctx["summary"]
    return (
        f"📊 <b>{month_label(ctx['year'], ctx['month'])}</b>\n\n"
        f"💚 Доходи: <b>{format_money(s['total_income'])}</b>\n"
        f"🔴 Витрати: <b>{format_money(s['total_expense'])}</b>\n"
        f"💰 Залишок: <b>{format_money(s['balance'])}</b>\n"
        f"📅 На день: <b>{format_money(s['safe_per_day'])}</b>\n"
        f"🚌 Транспорт: <b>{format_money(s['transport_total'])}</b>"
    )


async def income_text(user_id: int) -> str:
    ctx = await budget.load_month_context(user_id)
    s, ov = ctx["user"]["settings"], ctx["override"]
    extra = [f"• {format_date(e['date'])} — +{format_money(e['amount'])}"
             for e in ctx["extra_income"] if e["date"].startswith(ctx["month_key"])]
    text = (
        f"💰 <b>Доходи — {month_label(ctx['year'], ctx['month'])}</b>\n\n"
        f"Аванс ({ov.get('advance_day', s['advance_day'])}-е): <b>{format_money(ov.get('advance_amount', s['advance_amount']))}</b>\n"
        f"Зарплата ({ov.get('salary_day', s['salary_day'])}-е): <b>{format_money(ov.get('salary_amount', s['salary_amount']))}</b>\n"
    )
    if extra:
        text += "\n<b>Додаткові:</b>\n" + "\n".join(extra[:8])
    return text


async def transport_text(user_id: int) -> str:
    ctx = await budget.load_month_context(user_id)
    s = ctx["user"]["settings"]
    daily = s["transport_one_way"] * s["transport_trips_per_day"]
    auto_days = len(budget.get_auto_transport(s, ctx["year"], ctx["month"]))
    trips = [t for t in ctx["trips"] if t["date"].startswith(ctx["month_key"])]
    trips_total = sum(t["amount"] for t in trips)
    status = "увімкнено ✅" if s.get("transport_auto_enabled", True) else "вимкнено ❌"
    return (
        f"🚌 <b>Транспорт — {month_label(ctx['year'], ctx['month'])}</b>\n\n"
        f"Авто: <b>{status}</b> · Щодня <b>{format_money(daily)}</b>\n"
        f"За місяць: <b>{format_money(daily * auto_days + trips_total)}</b>"
    )


async def settings_text(user_id: int) -> str:
    s = (await database.get_user(user_id))["settings"]
    return (
        "⚙️ <b>Налаштування</b>\n\n"
        f"Аванс: <b>{format_money(s['advance_amount'])}</b> ({s['advance_day']}-е)\n"
        f"Зарплата: <b>{format_money(s['salary_amount'])}</b> ({s['salary_day']}-е)\n"
        f"Дорога: <b>{format_money(s['transport_one_way'])}</b> × {s['transport_trips_per_day']} поїздок"
    )


async def shift_month(user_id: int, delta: int) -> None:
    user = await database.get_user(user_id)
    y, m = user["view_year"], user["view_month"] + delta
    if m < 0: m, y = 11, y - 1
    elif m > 11: m, y = 0, y + 1
    await database.set_view_month(user_id, y, m)


async def save_quick_expense(user_id: int, category: str, amount: float, recurring: bool = False) -> str:
    await database.add_expense(user_id, {
        "id": new_id(),
        "date": date.today().isoformat(),
        "amount": amount,
        "category": category,
        "description": "",
        "recurring": recurring,
    })
    return f"✅ <b>−{format_money(amount)}</b> · {category} · сьогодні"


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await database.ensure_user(message.from_user.id)
    await message.answer(
        "👋 <b>Мій бюджет</b>\n\n"
        "⚡ <b>Швидко:</b> натисни «➕ Витрата» → категорія → сума (2 кліки)\n"
        "📱 Або відкрий додаток з iOS-інтерфейсом",
        reply_markup=reply_menu(),
    )
    await message.answer("Або обери тут:", reply_markup=main_menu())


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("🏠 Меню:", reply_markup=reply_menu())


@router.message(F.text.in_(REPLY_MAP.keys()))
async def on_reply_button(message: Message, state: FSMContext) -> None:
    await state.clear()
    action = REPLY_MAP[message.text]
    uid = message.from_user.id

    if action == "overview":
        await message.answer(await overview_text(uid), reply_markup=overview_menu())
    elif action == "quick_expense":
        user = await database.get_user(uid)
        await message.answer("1️⃣ Обери категорію:", reply_markup=quick_category_keyboard(user["settings"]["categories"]))
    elif action == "quick_income":
        await message.answer("💰 Обери суму доходу:", reply_markup=quick_income_amount_keyboard())
    elif action == "transport":
        user = await database.get_user(uid)
        s = user["settings"]
        await message.answer(
            await transport_text(uid),
            reply_markup=transport_quick_keyboard(s["transport_one_way"]),
        )
    elif action == "settings":
        await message.answer(await settings_text(uid), reply_markup=settings_menu())


@router.callback_query(F.data == "cancel")
@router.callback_query(F.data == "menu:main")
async def on_main(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("🏠 Меню:", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "quick:expense")
async def quick_expense_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user = await database.get_user(callback.from_user.id)
    await callback.message.edit_text(
        "⚡ <b>Швидка витрата</b>\n\n1️⃣ Обери категорію:",
        reply_markup=quick_category_keyboard(user["settings"]["categories"]),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("quick:cat:"))
async def quick_expense_category(callback: CallbackQuery) -> None:
    category = callback.data.split(":", 2)[2]
    await callback.message.edit_text(
        f"2️⃣ <b>{category}</b> — обери суму:",
        reply_markup=quick_amount_keyboard(category),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("quick:amt:"))
async def quick_expense_save(callback: CallbackQuery) -> None:
    _, _, category, amount_str = callback.data.split(":", 3)
    amount = float(amount_str)
    text = await save_quick_expense(callback.from_user.id, category, amount)
    await callback.message.edit_text(text, reply_markup=after_save_keyboard())
    await callback.answer("Збережено!")


@router.callback_query(F.data.startswith("quick:custom:"))
async def quick_expense_custom(callback: CallbackQuery, state: FSMContext) -> None:
    category = callback.data.split(":", 2)[2]
    await state.set_state(QuickCustomForm.amount)
    await state.update_data(quick_type="expense", category=category)
    await callback.message.edit_text(f"✏️ Введи суму для <b>{category}</b> (₴):", reply_markup=cancel_keyboard())
    await callback.answer()


@router.callback_query(F.data == "quick:income")
async def quick_income_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("💰 Обери суму:", reply_markup=quick_income_amount_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("quick:inc:"))
async def quick_income_save(callback: CallbackQuery, state: FSMContext) -> None:
    part = callback.data.split(":")[2]
    if part == "custom":
        await state.set_state(QuickCustomForm.amount)
        await state.update_data(quick_type="income")
        await callback.message.edit_text("✏️ Введи суму доходу (₴):", reply_markup=cancel_keyboard())
        await callback.answer()
        return
    amount = float(part)
    await database.add_extra_income(callback.from_user.id, {
        "id": new_id(), "date": date.today().isoformat(), "amount": amount, "description": "",
    })
    await callback.message.edit_text(f"✅ <b>+{format_money(amount)}</b> · сьогодні", reply_markup=after_save_keyboard())
    await callback.answer("Збережено!")


@router.message(QuickCustomForm.amount)
async def quick_custom_amount(message: Message, state: FSMContext) -> None:
    amount = parse_amount(message.text)
    if amount is None:
        return await message.answer("Введи число, напр. 350")
    data = await state.get_data()
    await state.clear()
    if data.get("quick_type") == "income":
        await database.add_extra_income(message.from_user.id, {
            "id": new_id(), "date": date.today().isoformat(), "amount": amount, "description": "",
        })
        await message.answer(f"✅ <b>+{format_money(amount)}</b>", reply_markup=reply_menu())
    else:
        text = await save_quick_expense(message.from_user.id, data["category"], amount)
        await message.answer(text, reply_markup=reply_menu())


@router.callback_query(F.data == "menu:overview")
async def on_overview(callback: CallbackQuery) -> None:
    await callback.message.edit_text(await overview_text(callback.from_user.id), reply_markup=overview_menu())
    await callback.answer()


@router.callback_query(F.data.startswith("month:"))
async def on_month(callback: CallbackQuery) -> None:
    await shift_month(callback.from_user.id, -1 if callback.data.endswith("prev") else 1)
    await callback.message.edit_text(await overview_text(callback.from_user.id), reply_markup=overview_menu())
    await callback.answer()


@router.callback_query(F.data == "overview:events")
async def on_events(callback: CallbackQuery) -> None:
    ctx = await budget.load_month_context(callback.from_user.id)
    today = date.today().isoformat()
    events = [e for e in ctx["summary"]["events"] if e["date"] >= today][:15]
    if not events:
        text = "📅 Немає майбутніх подій."
    else:
        lines = [f"{format_date(e['date'])} {e['description']}: "
                 f"{'+' if e['type']=='income' else '-'}{format_money(e['amount'])}" for e in events]
        text = "📅 <b>Події</b>\n\n" + "\n".join(lines)
    await callback.message.edit_text(text, reply_markup=overview_menu())
    await callback.answer()


@router.callback_query(F.data == "menu:income")
async def on_income(callback: CallbackQuery) -> None:
    await callback.message.edit_text(await income_text(callback.from_user.id), reply_markup=income_menu())
    await callback.answer()


@router.callback_query(F.data.startswith("income:edit:"))
async def on_income_edit(callback: CallbackQuery, state: FSMContext) -> None:
    field = callback.data.split(":")[-1]
    await state.set_state(MonthOverrideForm.value)
    await state.update_data(field=field)
    await callback.message.edit_text(f"✏️ {OVERRIDE_LABELS.get(field, field)}:", reply_markup=cancel_keyboard())
    await callback.answer()


@router.callback_query(F.data == "income:add_extra")
async def on_add_extra(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("💰 Обери суму:", reply_markup=quick_income_amount_keyboard())
    await callback.answer()


@router.callback_query(F.data == "menu:expenses")
async def on_expenses(callback: CallbackQuery) -> None:
    ctx = await budget.load_month_context(callback.from_user.id)
    await callback.message.edit_text(
        f"💸 <b>Витрати</b>\n\nВсього: <b>{format_money(ctx['summary']['total_expense'])}</b>",
        reply_markup=expenses_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "expense:add")
async def on_expense_add(callback: CallbackQuery, state: FSMContext) -> None:
    user = await database.get_user(callback.from_user.id)
    await state.clear()
    await callback.message.edit_text("1️⃣ Категорія:", reply_markup=quick_category_keyboard(user["settings"]["categories"]))
    await callback.answer()


@router.callback_query(F.data == "expense:list")
async def on_expense_list(callback: CallbackQuery) -> None:
    ctx = await budget.load_month_context(callback.from_user.id)
    lines = [f"• {format_date(e['date'])} — {e['category']}: -{format_money(e['amount'])}"
             for e in ctx["expenses"] if not e["recurring"] and e["date"].startswith(ctx["month_key"])][:12]
    await callback.message.edit_text("📋 <b>Витрати</b>\n\n" + ("\n".join(lines) if lines else "Порожньо."), reply_markup=expenses_menu())
    await callback.answer()


@router.callback_query(F.data == "menu:transport")
async def on_transport(callback: CallbackQuery) -> None:
    user = await database.get_user(callback.from_user.id)
    s = user["settings"]
    await callback.message.edit_text(
        await transport_text(callback.from_user.id),
        reply_markup=transport_quick_keyboard(s["transport_one_way"]),
    )
    await callback.answer()


@router.callback_query(F.data == "transport:toggle_auto")
async def on_transport_toggle(callback: CallbackQuery) -> None:
    user = await database.get_user(callback.from_user.id)
    s = user["settings"]
    s["transport_auto_enabled"] = not s.get("transport_auto_enabled", True)
    await database.update_settings(callback.from_user.id, s)
    await callback.message.edit_text(await transport_text(callback.from_user.id), reply_markup=transport_menu(s["transport_auto_enabled"]))
    await callback.answer()


@router.callback_query(F.data.startswith("transport:quick:"))
async def transport_quick_save(callback: CallbackQuery) -> None:
    amount = float(callback.data.split(":")[2])
    await database.add_transport_trip(callback.from_user.id, {
        "id": new_id(), "date": date.today().isoformat(), "amount": amount, "description": "Дорога",
    })
    await callback.message.edit_text(f"✅ <b>−{format_money(amount)}</b> · транспорт", reply_markup=after_save_keyboard())
    await callback.answer()


@router.callback_query(F.data == "transport:quick_trip")
async def on_transport_quick_menu(callback: CallbackQuery) -> None:
    user = await database.get_user(callback.from_user.id)
    s = user["settings"]
    daily = s["transport_one_way"] * s["transport_trips_per_day"]
    await callback.message.edit_text(
        f"🚌 Додати поїздку за <b>{format_money(daily)}</b>?",
        reply_markup=transport_quick_keyboard(s["transport_one_way"]),
    )
    await callback.answer()


@router.callback_query(F.data == "transport:add_trip")
async def on_trip_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(TransportTripForm.amount)
    await callback.message.edit_text("🚌 Сума (₴):", reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(TransportTripForm.amount)
async def trip_amount(message: Message, state: FSMContext) -> None:
    amount = parse_amount(message.text)
    if amount is None: return await message.answer("Введи число")
    await database.add_transport_trip(message.from_user.id, {
        "id": new_id(), "date": date.today().isoformat(), "amount": amount, "description": "",
    })
    await state.clear()
    await message.answer(f"✅ −{format_money(amount)}", reply_markup=reply_menu())


@router.callback_query(F.data == "menu:settings")
async def on_settings(callback: CallbackQuery) -> None:
    await callback.message.edit_text(await settings_text(callback.from_user.id), reply_markup=settings_menu())
    await callback.answer()


@router.callback_query(F.data.startswith("settings:"))
async def on_settings_field(callback: CallbackQuery, state: FSMContext) -> None:
    field = callback.data.split(":")[1]
    await state.set_state(SettingsForm.value)
    await state.update_data(field=field)
    await callback.message.edit_text(f"✏️ {SETTINGS_LABELS.get(field, field)}:", reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(SettingsForm.value)
async def settings_val(message: Message, state: FSMContext) -> None:
    field = (await state.get_data())["field"]
    user = await database.get_user(message.from_user.id)
    s = user["settings"]
    if field.endswith("_day") or field == "transport_trips_per_day":
        val = parse_day(message.text)
        if val is None or (field == "transport_trips_per_day" and val > 10):
            return await message.answer("Невірне число")
        s[field] = val
    else:
        val = parse_amount(message.text)
        if val is None: return await message.answer("Введи число")
        s[field] = val
    await database.update_settings(message.from_user.id, s)
    await state.clear()
    await message.answer("✅ Збережено!", reply_markup=reply_menu())


@router.message(MonthOverrideForm.value)
async def override_val(message: Message, state: FSMContext) -> None:
    field = (await state.get_data())["field"]
    val = parse_amount(message.text)
    if val is None: return await message.answer("Введи число")
    ctx = await budget.load_month_context(message.from_user.id)
    await database.set_month_override(message.from_user.id, ctx["month_key"], {field: val})
    await state.clear()
    await message.answer(f"✅ {format_money(val)}", reply_markup=reply_menu())
