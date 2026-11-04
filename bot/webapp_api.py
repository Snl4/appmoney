import hashlib
import hmac
import json
import logging
from pathlib import Path
from urllib.parse import parse_qsl

from aiohttp import web

from bot import budget, database
from bot.budget import format_money, month_label, new_id
from bot.battlepass_api import setup_battlepass_routes

logger = logging.getLogger("webapp-api")
WEBAPP_DIR = Path(__file__).resolve().parent.parent / "webapp"

CATEGORY_ICONS = {
    "Транспорт": "🚌", "Їжа": "🍔", "Комунальні": "💡", "Оренда": "🏠",
    "Розваги": "🎮", "Здоров'я": "💊", "Інше": "📦",
}


def validate_init_data(init_data: str, bot_token: str) -> dict | None:
    if not init_data or not bot_token:
        return None
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", "")
        data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calculated = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        if calculated != received_hash:
            return None
        user = json.loads(parsed.get("user", "{}"))
        return {"user_id": user.get("id"), "user": user}
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


async def get_user_id(request: web.Request) -> int | None:
    auth = validate_init_data(request.headers.get("X-Telegram-Init-Data", ""), request.app["bot_token"])
    if auth and auth.get("user_id"):
        return int(auth["user_id"])
    return None


def json_response(data: dict, status: int = 200) -> web.Response:
    return web.json_response(data, status=status)


async def handle_index(_: web.Request) -> web.FileResponse:
    return web.FileResponse(WEBAPP_DIR / "index.html")


async def api_summary(request: web.Request) -> web.Response:
    user_id = await get_user_id(request)
    if not user_id:
        return json_response({"error": "unauthorized"}, 401)
    ctx = await budget.load_month_context(user_id)
    s = ctx["summary"]
    return json_response({
        "month": budget.month_label(ctx["year"], ctx["month"]),
        "year": ctx["year"],
        "month_index": ctx["month"],
        "total_income": s["total_income"],
        "total_expense": s["total_expense"],
        "balance": s["balance"],
        "safe_per_day": s["safe_per_day"],
        "transport_total": s["transport_total"],
        "formatted": {
            "income": format_money(s["total_income"]),
            "expense": format_money(s["total_expense"]),
            "balance": format_money(s["balance"]),
            "daily": format_money(s["safe_per_day"]),
            "transport": format_money(s["transport_total"]),
        },
    })


async def api_events(request: web.Request) -> web.Response:
    user_id = await get_user_id(request)
    if not user_id:
        return json_response({"error": "unauthorized"}, 401)
    ctx = await budget.load_month_context(user_id)
    events = []
    for e in ctx["summary"]["events"][:50]:
        events.append({
            "id": e.get("id", ""),
            "date": e["date"],
            "amount": e["amount"],
            "type": e["type"],
            "description": e.get("description", ""),
            "category": e.get("category", ""),
            "auto": e.get("auto", False),
            "formatted_date": budget.format_date(e["date"]),
            "formatted_amount": format_money(e["amount"]),
        })
    return json_response({"events": events})


async def api_settings(request: web.Request) -> web.Response:
    user_id = await get_user_id(request)
    if not user_id:
        return json_response({"error": "unauthorized"}, 401)
    user = await database.get_user(user_id)
    ctx = await budget.load_month_context(user_id)
    s = user["settings"]
    ov = ctx["override"]
    return json_response({
        "settings": s,
        "override": ov,
        "categories": [{"name": c, "icon": CATEGORY_ICONS.get(c, "📦")} for c in s["categories"]],
        "formatted": {
            "advance": format_money(ov.get("advance_amount", s["advance_amount"])),
            "salary": format_money(ov.get("salary_amount", s["salary_amount"])),
        },
    })


async def api_update_settings(request: web.Request) -> web.Response:
    user_id = await get_user_id(request)
    if not user_id:
        return json_response({"error": "unauthorized"}, 401)
    body = await request.json()
    user = await database.get_user(user_id)
    s = user["settings"]
    for key in ("advance_amount", "advance_day", "salary_amount", "salary_day",
                "transport_one_way", "transport_trips_per_day", "transport_auto_enabled"):
        if key in body:
            s[key] = body[key]
    await database.update_settings(user_id, s)
    if "advance_amount" in body or "salary_amount" in body:
        ctx = await budget.load_month_context(user_id)
        patch = {}
        if "advance_amount" in body:
            patch["advance_amount"] = body["advance_amount"]
        if "salary_amount" in body:
            patch["salary_amount"] = body["salary_amount"]
        await database.set_month_override(user_id, ctx["month_key"], patch)
    return json_response({"ok": True})


async def api_add_expense(request: web.Request) -> web.Response:
    user_id = await get_user_id(request)
    if not user_id:
        return json_response({"error": "unauthorized"}, 401)
    body = await request.json()
    from datetime import date
    item = {
        "id": new_id(),
        "date": body.get("date") or date.today().isoformat(),
        "amount": float(body["amount"]),
        "category": body["category"],
        "description": body.get("description", ""),
        "recurring": bool(body.get("recurring", False)),
    }
    await database.add_expense(user_id, item)
    return json_response({"ok": True, "id": item["id"]})


async def api_add_income(request: web.Request) -> web.Response:
    user_id = await get_user_id(request)
    if not user_id:
        return json_response({"error": "unauthorized"}, 401)
    body = await request.json()
    from datetime import date
    item = {
        "id": new_id(),
        "date": body.get("date") or date.today().isoformat(),
        "amount": float(body["amount"]),
        "description": body.get("description", "Додатковий дохід"),
    }
    await database.add_extra_income(user_id, item)
    return json_response({"ok": True, "id": item["id"]})


async def api_delete_expense(request: web.Request) -> web.Response:
    user_id = await get_user_id(request)
    if not user_id:
        return json_response({"error": "unauthorized"}, 401)
    expense_id = request.match_info["id"]
    await database.delete_expense(user_id, expense_id)
    return json_response({"ok": True})


async def api_shift_month(request: web.Request) -> web.Response:
    user_id = await get_user_id(request)
    if not user_id:
        return json_response({"error": "unauthorized"}, 401)
    body = await request.json()
    user = await database.get_user(user_id)
    y, m = user["view_year"], user["view_month"] + int(body.get("delta", 0))
    if m < 0: m, y = 11, y - 1
    elif m > 11: m, y = 0, y + 1
    await database.set_view_month(user_id, y, m)
    return json_response({"ok": True, "month": budget.month_label(y, m)})


def create_app(bot_token: str) -> web.Application:
    app = web.Application()
    app["bot_token"] = bot_token
    app.router.add_get("/", handle_index)
    setup_battlepass_routes(app)
    app.router.add_static("/static/", WEBAPP_DIR, name="static")
    app.router.add_get("/api/summary", api_summary)
    app.router.add_get("/api/events", api_events)
    app.router.add_get("/api/settings", api_settings)
    app.router.add_put("/api/settings", api_update_settings)
    app.router.add_post("/api/expense", api_add_expense)
    app.router.add_post("/api/income", api_add_income)
    app.router.add_delete("/api/expense/{id}", api_delete_expense)
    app.router.add_post("/api/month", api_shift_month)
    return app
