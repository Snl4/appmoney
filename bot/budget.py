from __future__ import annotations

import uuid
from datetime import date

MONTH_NAMES = [
    "Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
    "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень",
]


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def month_key(year: int, month: int) -> str:
    return f"{year}-{month + 1:02d}"


def days_in_month(year: int, month: int) -> int:
    if month == 11:
        return 31
    return (date(year, month + 2, 1) - date(year, month + 1, 1)).days


def pad_day(year: int, month: int, day: int) -> str:
    return f"{year}-{month + 1:02d}-{min(day, days_in_month(year, month)):02d}"


def format_money(amount: float) -> str:
    return f"{amount:,.0f} ₴".replace(",", " ")


def format_date(iso: str) -> str:
    y, m, d = map(int, iso.split("-"))
    return date(y, m, d).strftime("%d.%m")


def month_label(year: int, month: int) -> str:
    return f"{MONTH_NAMES[month]} {year}"


def get_salary_income(settings: dict, override: dict, year: int, month: int) -> list[dict]:
    advance = override.get("advance_amount", settings["advance_amount"])
    salary = override.get("salary_amount", settings["salary_amount"])
    advance_day = override.get("advance_day", settings["advance_day"])
    salary_day = override.get("salary_day", settings["salary_day"])
    items = []
    if advance > 0:
        items.append({"id": f"advance-{year}-{month}", "date": pad_day(year, month, advance_day),
                       "amount": advance, "description": "Аванс", "type": "income", "auto": True})
    if salary > 0:
        items.append({"id": f"salary-{year}-{month}", "date": pad_day(year, month, salary_day),
                       "amount": salary, "description": "Зарплата", "type": "income", "auto": True})
    return items


def get_auto_transport(settings: dict, year: int, month: int) -> list[dict]:
    if not settings.get("transport_auto_enabled", True):
        return []
    daily = settings["transport_one_way"] * settings["transport_trips_per_day"]
    if daily <= 0:
        return []
    work_days = set(settings.get("transport_work_days", [1, 2, 3, 4, 5]))
    items = []
    for d in range(1, days_in_month(year, month) + 1):
        dt = date(year, month + 1, d)
        wd = (dt.weekday() + 1) % 7
        if wd not in work_days:
            continue
        iso = pad_day(year, month, d)
        items.append({
            "id": f"transport-auto-{iso}", "date": iso, "amount": daily,
            "category": "Транспорт",
            "description": f"Дорога ({settings['transport_trips_per_day']}×{settings['transport_one_way']:.0f} ₴)",
            "type": "expense", "auto": True,
        })
    return items


def get_recurring_expenses(expenses: list[dict], year: int, month: int) -> list[dict]:
    key = month_key(year, month)
    return [
        {**e, "id": f"recurring-{e['id']}-{key}", "date": pad_day(year, month, int(e["date"].split("-")[2])),
         "type": "expense", "auto": True}
        for e in expenses if e["recurring"]
    ]


def get_one_time_expenses(expenses: list[dict], year: int, month: int) -> list[dict]:
    prefix = month_key(year, month)
    return [{**e, "type": "expense", "auto": False} for e in expenses
            if not e["recurring"] and e["date"].startswith(prefix)]


def get_extra_income_events(items: list[dict], year: int, month: int) -> list[dict]:
    prefix = month_key(year, month)
    return [{**e, "type": "income", "auto": False,
             "description": e.get("description") or "Додатковий дохід"}
            for e in items if e["date"].startswith(prefix)]


def get_transport_trips_events(trips: list[dict], year: int, month: int) -> list[dict]:
    prefix = month_key(year, month)
    return [{"id": t["id"], "date": t["date"], "amount": t["amount"], "category": "Транспорт",
             "description": t.get("description") or "Разова поїздка", "type": "expense", "auto": False}
            for t in trips if t["date"].startswith(prefix)]


def get_all_events(settings, override, expenses, extra_income, trips, year, month) -> list[dict]:
    events = [
        *get_salary_income(settings, override, year, month),
        *get_extra_income_events(extra_income, year, month),
        *get_recurring_expenses(expenses, year, month),
        *get_one_time_expenses(expenses, year, month),
        *get_auto_transport(settings, year, month),
        *get_transport_trips_events(trips, year, month),
    ]
    events.sort(key=lambda e: (e["date"], 0 if e["type"] == "income" else 1))
    return events


def build_daily_balance(events: list[dict], year: int, month: int) -> list[dict]:
    by_date = {pad_day(year, month, d): {"income": 0.0, "expense": 0.0} for d in range(1, days_in_month(year, month) + 1)}
    for ev in events:
        if ev["date"] not in by_date:
            continue
        if ev["type"] == "income":
            by_date[ev["date"]]["income"] += ev["amount"]
        else:
            by_date[ev["date"]]["expense"] += ev["amount"]
    running = 0.0
    days = []
    for d in range(1, days_in_month(year, month) + 1):
        iso = pad_day(year, month, d)
        running += by_date[iso]["income"] - by_date[iso]["expense"]
        days.append({"date": iso, "balance": running})
    return days


def get_summary(settings, override, expenses, extra_income, trips, year, month) -> dict:
    events = get_all_events(settings, override, expenses, extra_income, trips, year, month)
    total_income = sum(e["amount"] for e in events if e["type"] == "income")
    total_expense = sum(e["amount"] for e in events if e["type"] == "expense")
    balance = total_income - total_expense
    today = date.today()
    is_current = today.year == year and today.month == month + 1
    today_iso = today.isoformat()
    days = build_daily_balance(events, year, month)
    balance_now = balance
    if is_current:
        for d in days:
            if d["date"] <= today_iso:
                balance_now = d["balance"]
    remaining = (days_in_month(year, month) - today.day + 1) if is_current else days_in_month(year, month)
    future_exp = sum(e["amount"] for e in events if e["type"] == "expense" and e["date"] > today_iso) if is_current else 0
    future_inc = sum(e["amount"] for e in events if e["type"] == "income" and e["date"] > today_iso) if is_current else 0
    safe = max(0, (balance_now + future_inc - future_exp) / remaining) if remaining > 0 else 0
    transport = sum(e["amount"] for e in events if e["type"] == "expense" and e.get("category") == "Транспорт")
    return {"total_income": total_income, "total_expense": total_expense, "balance": balance,
            "balance_now": balance_now, "safe_per_day": safe, "transport_total": transport, "events": events}


async def load_month_context(user_id: int) -> dict:
    from bot.database import get_month_override, get_user, list_expenses, list_extra_income, list_transport_trips
    user = await get_user(user_id)
    year, month = user["view_year"], user["view_month"]
    key = month_key(year, month)
    override = await get_month_override(user_id, key)
    expenses = await list_expenses(user_id)
    extra = await list_extra_income(user_id)
    trips = await list_transport_trips(user_id)
    summary = get_summary(user["settings"], override, expenses, extra, trips, year, month)
    return {"user": user, "year": year, "month": month, "month_key": key, "override": override,
            "expenses": expenses, "extra_income": extra, "trips": trips, "summary": summary}
