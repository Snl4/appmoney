"""HTTP API for Battle Pass player UI, admin panel and Minecraft event ingest."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from aiohttp import web

from bot import battlepass_db as db
from bot import battlepass_logic as logic

logger = logging.getLogger("battlepass-api")
WEBAPP_DIR = Path(__file__).resolve().parent.parent / "webapp"


def _admin_key() -> str:
    return os.getenv("BATTLEPASS_ADMIN_KEY", "capy-admin-dev")


def _minecraft_key() -> str:
    return os.getenv("MINECRAFT_API_KEY", "capy-mc-dev")


def _check_key(request: web.Request, expected: str) -> bool:
    got = request.headers.get("X-API-Key") or request.query.get("api_key") or ""
    return bool(expected) and got == expected


def json_error(message: str, status: int = 400) -> web.Response:
    return web.json_response({"ok": False, "error": message}, status=status)


async def handle_battlepass_page(_: web.Request) -> web.FileResponse:
    return web.FileResponse(WEBAPP_DIR / "battlepass.html")


async def handle_admin_page(_: web.Request) -> web.FileResponse:
    return web.FileResponse(WEBAPP_DIR / "battlepass_admin.html")


async def api_event_types(_: web.Request) -> web.Response:
    return web.json_response({"event_types": list(db.EVENT_TYPES)})


async def api_active_view(request: web.Request) -> web.Response:
    player = (request.query.get("player") or "Steve").strip()
    view = await logic.build_player_view(player)
    return web.json_response({"ok": True, **view})


async def api_claim_quest(request: web.Request) -> web.Response:
    body = await request.json()
    player = str(body.get("player") or "").strip()
    quest_id = str(body.get("quest_id") or "").strip()
    if not player or not quest_id:
        return json_error("player_and_quest_required")
    result = await logic.claim_quest(player, quest_id)
    status = 200 if result.get("ok") else 400
    return web.json_response(result, status=status)


async def api_claim_reward(request: web.Request) -> web.Response:
    body = await request.json()
    player = str(body.get("player") or "").strip()
    level = int(body.get("level") or 0)
    premium = bool(body.get("premium"))
    if not player or level < 1:
        return json_error("player_and_level_required")
    result = await logic.claim_reward(player, level, premium)
    status = 200 if result.get("ok") else 400
    return web.json_response(result, status=status)


async def api_set_premium(request: web.Request) -> web.Response:
    body = await request.json()
    player = str(body.get("player") or "").strip()
    if not player:
        return json_error("player_required")
    premium = bool(body.get("premium", True))
    await db.set_player_premium(player, premium)
    view = await logic.build_player_view(player)
    return web.json_response({"ok": True, "view": view})


async def api_ingest_events(request: web.Request) -> web.Response:
    """Minecraft plugin posts here when players do things in-game."""
    if not _check_key(request, _minecraft_key()):
        return json_error("unauthorized", 401)
    body = await request.json()
    events = body.get("events")
    if events is None and body.get("player"):
        events = [body]
    if not isinstance(events, list) or not events:
        return json_error("events_required")
    result = await logic.ingest_events(events, source=body.get("source") or "minecraft")
    return web.json_response(result)


async def api_admin_overview(request: web.Request) -> web.Response:
    if not _check_key(request, _admin_key()):
        return json_error("unauthorized", 401)
    return web.json_response({"ok": True, **(await logic.admin_overview())})


async def api_admin_create_season(request: web.Request) -> web.Response:
    if not _check_key(request, _admin_key()):
        return json_error("unauthorized", 401)
    body = await request.json()
    required = ("number", "name", "starts_at", "ends_at")
    if any(k not in body for k in required):
        return json_error("missing_fields")
    season = await db.create_season(body)
    return web.json_response({"ok": True, "season": season})


async def api_admin_update_season(request: web.Request) -> web.Response:
    if not _check_key(request, _admin_key()):
        return json_error("unauthorized", 401)
    season_id = request.match_info["id"]
    body = await request.json()
    season = await db.update_season(season_id, body)
    if not season:
        return json_error("not_found", 404)
    return web.json_response({"ok": True, "season": season})


async def api_admin_create_quest(request: web.Request) -> web.Response:
    if not _check_key(request, _admin_key()):
        return json_error("unauthorized", 401)
    body = await request.json()
    try:
        quest = await db.create_quest(body)
    except (KeyError, ValueError) as exc:
        return json_error(str(exc))
    return web.json_response({"ok": True, "quest": quest})


async def api_admin_update_quest(request: web.Request) -> web.Response:
    if not _check_key(request, _admin_key()):
        return json_error("unauthorized", 401)
    quest_id = request.match_info["id"]
    body = await request.json()
    try:
        quest = await db.update_quest(quest_id, body)
    except ValueError as exc:
        return json_error(str(exc))
    if not quest:
        return json_error("not_found", 404)
    return web.json_response({"ok": True, "quest": quest})


async def api_admin_delete_quest(request: web.Request) -> web.Response:
    if not _check_key(request, _admin_key()):
        return json_error("unauthorized", 401)
    ok = await db.delete_quest(request.match_info["id"])
    if not ok:
        return json_error("not_found", 404)
    return web.json_response({"ok": True})


async def api_admin_upsert_reward(request: web.Request) -> web.Response:
    if not _check_key(request, _admin_key()):
        return json_error("unauthorized", 401)
    body = await request.json()
    try:
        reward = await db.upsert_reward(body)
    except KeyError as exc:
        return json_error(str(exc))
    return web.json_response({"ok": True, "reward": reward})


async def api_admin_delete_reward(request: web.Request) -> web.Response:
    if not _check_key(request, _admin_key()):
        return json_error("unauthorized", 401)
    ok = await db.delete_reward(request.match_info["id"])
    if not ok:
        return json_error("not_found", 404)
    return web.json_response({"ok": True})


async def api_admin_simulate(request: web.Request) -> web.Response:
    """Admin helper: simulate Minecraft events without the plugin."""
    if not _check_key(request, _admin_key()):
        return json_error("unauthorized", 401)
    body = await request.json()
    events = body.get("events") or [body]
    result = await logic.ingest_events(events, source="admin_simulate")
    player = None
    if events and isinstance(events, list):
        player = events[0].get("player")
    view = await logic.build_player_view(player) if player else None
    return web.json_response({**result, "view": view})


def setup_battlepass_routes(app: web.Application) -> None:
    app.router.add_get("/battlepass", handle_battlepass_page)
    app.router.add_get("/battlepass/", handle_battlepass_page)
    app.router.add_get("/battlepass/admin", handle_admin_page)
    app.router.add_get("/battlepass/admin/", handle_admin_page)

    app.router.add_get("/api/battlepass/event-types", api_event_types)
    app.router.add_get("/api/battlepass/view", api_active_view)
    app.router.add_post("/api/battlepass/claim-quest", api_claim_quest)
    app.router.add_post("/api/battlepass/claim-reward", api_claim_reward)
    app.router.add_post("/api/battlepass/premium", api_set_premium)
    app.router.add_post("/api/battlepass/events", api_ingest_events)

    app.router.add_get("/api/battlepass/admin/overview", api_admin_overview)
    app.router.add_post("/api/battlepass/admin/seasons", api_admin_create_season)
    app.router.add_put("/api/battlepass/admin/seasons/{id}", api_admin_update_season)
    app.router.add_post("/api/battlepass/admin/quests", api_admin_create_quest)
    app.router.add_put("/api/battlepass/admin/quests/{id}", api_admin_update_quest)
    app.router.add_delete("/api/battlepass/admin/quests/{id}", api_admin_delete_quest)
    app.router.add_post("/api/battlepass/admin/rewards", api_admin_upsert_reward)
    app.router.add_delete("/api/battlepass/admin/rewards/{id}", api_admin_delete_reward)
    app.router.add_post("/api/battlepass/admin/simulate", api_admin_simulate)
