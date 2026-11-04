"""Battle Pass business logic: XP, quest matching, event ingest, claims."""

from __future__ import annotations

from typing import Any

from bot import battlepass_db as db

# Real Premium Pass benefits (wired into claim/activate flows).
PREMIUM_XP_BONUS = 0.20  # +20% XP from quests
PREMIUM_LEVEL_BOOST = 5  # instant boost at least to level 5
PREMIUM_LP_COMMANDS = [
    "lp user %player% parent add bp.premium",
    "lp user %player% permission set bp.skin.premium true",
    "lp user %player% permission set bp.cosmetic.exclusive true",
]
PREMIUM_REVOKE_COMMANDS = [
    "lp user %player% parent remove bp.premium",
]


def xp_needed_for_level(season: dict, level: int) -> int:
    """XP required to go from `level` to `level + 1`."""
    base = int(season["xp_base"])
    growth = float(season["xp_growth"])
    if level <= 1:
        return base
    return max(1, int(round(base * (growth ** (level - 1)))))


def apply_xp(season: dict, state: dict, gained: int) -> dict:
    state = dict(state)
    state["xp"] = int(state["xp"]) + int(gained)
    needed = xp_needed_for_level(season, int(state["level"]))
    while state["xp"] >= needed:
        state["xp"] -= needed
        state["level"] = int(state["level"]) + 1
        needed = xp_needed_for_level(season, int(state["level"]))
    return state


def reward_claim_key(level: int, premium: bool) -> str:
    return f"{level}:{1 if premium else 0}"


def meta_matches(quest_filter: dict, event_meta: dict) -> bool:
    if not quest_filter:
        return True
    for key, expected in quest_filter.items():
        if event_meta.get(key) != expected:
            return False
    return True


async def build_player_view(minecraft_name: str, season: dict | None = None) -> dict:
    season = season or await db.get_active_season()
    if not season:
        return {"season": None, "player": None, "rewards": [], "quests": {"daily": [], "weekly": [], "season": []}}

    player = await db.ensure_player(minecraft_name)
    state = await db.get_player_season(minecraft_name, season["id"])
    rewards = await db.list_rewards(season["id"])
    claimed = set(state.get("claimed_rewards") or [])

    reward_view = []
    for reward in rewards:
        key = reward_claim_key(reward["level"], reward["premium"])
        locked = reward["level"] > state["level"] or (reward["premium"] and not player["premium"])
        reward_view.append(
            {
                **reward,
                "claimed": key in claimed,
                "locked": locked,
                "claimable": (not locked) and key not in claimed,
            }
        )

    quests = await db.list_quests(season["id"], active_only=True)
    grouped: dict[str, list] = {"daily": [], "weekly": [], "season": []}
    for quest in quests:
        progress = await db.get_quest_progress(minecraft_name, quest)
        current = min(int(progress["progress"]), int(quest["target"]))
        done = current >= int(quest["target"])
        base_xp = int(quest["xp_reward"])
        xp_shown = int(round(base_xp * (1 + PREMIUM_XP_BONUS))) if player["premium"] else base_xp
        item = {
            "id": quest["id"],
            "title": quest["title"],
            "desc": quest["description"],
            "icon": quest["icon"],
            "kind": quest["kind"],
            "event_type": quest["event_type"],
            "current": current,
            "target": int(quest["target"]),
            "xp": xp_shown,
            "xp_base": base_xp,
            "xp_bonus": max(0, xp_shown - base_xp),
            "claimed": bool(progress["claimed"]),
            "claimable": done and not progress["claimed"],
            "period_key": progress["period_key"],
            "resets": quest["resets"],
        }
        grouped.setdefault(quest["kind"], []).append(item)

    needed = xp_needed_for_level(season, int(state["level"]))
    free_claimable = sum(1 for r in reward_view if r["claimable"] and not r["premium"])
    prem_claimable = sum(1 for r in reward_view if r["claimable"] and r["premium"])
    return {
        "season": {
            "id": season["id"],
            "number": season["number"],
            "name": season["name"],
            "description": season["description"],
            "starts_at": season["starts_at"],
            "ends_at": season["ends_at"],
            "xp_base": season["xp_base"],
            "xp_growth": season["xp_growth"],
        },
        "player": {
            "minecraft_name": player["minecraft_name"],
            "premium": player["premium"],
            "level": state["level"],
            "xp": state["xp"],
            "xp_to_next": needed,
            "xp_bonus_percent": int(PREMIUM_XP_BONUS * 100) if player["premium"] else 0,
            "benefits": {
                "dual_track": True,
                "exclusive_skins": bool(player["premium"]),
                "xp_bonus_percent": int(PREMIUM_XP_BONUS * 100) if player["premium"] else 0,
                "level_boost_to": PREMIUM_LEVEL_BOOST if player["premium"] else None,
            },
        },
        "rewards": reward_view,
        "quests": grouped,
        "stats": {
            "free_claimable": free_claimable,
            "premium_claimable": prem_claimable,
        },
    }


async def ingest_events(events: list[dict], source: str = "minecraft") -> dict:
    """
    Apply Minecraft (or manual) events to matching active quests.

    Event shape:
      {
        "player": "Steve",
        "type": "walk_blocks",
        "amount": 12,
        "meta": {"biome": "plains"}
      }
    """
    season = await db.get_active_season()
    if not season:
        return {"ok": False, "error": "no_active_season", "updated": []}

    quests = await db.list_quests(season["id"], active_only=True)
    updated: list[dict] = []

    for raw in events:
        player = str(raw.get("player") or "").strip()
        event_type = str(raw.get("type") or raw.get("event_type") or "").strip()
        amount = int(raw.get("amount") or 0)
        meta = raw.get("meta") or {}
        if not player or not event_type or amount <= 0:
            continue
        if event_type not in db.EVENT_TYPES:
            continue

        await db.ensure_player(player)
        await db.log_event(player, event_type, amount, meta, source)

        for quest in quests:
            if quest["event_type"] != event_type:
                continue
            if not meta_matches(quest.get("meta_filter") or {}, meta):
                continue
            # Unique biome visits: amount should be 1 per new biome; plugin sends distinct keys.
            if event_type == "visit_biome":
                # Count unique biomes via meta.biome stored in progress indirectly:
                # plugin should send amount=1 only for first visit this period.
                pass

            row = await db.get_quest_progress(player, quest)
            if row["claimed"]:
                continue
            before = int(row["progress"])
            row["progress"] = min(int(quest["target"]), before + amount)
            if row["progress"] != before:
                await db.save_quest_progress(row)
                updated.append(
                    {
                        "player": player,
                        "quest_id": quest["id"],
                        "title": quest["title"],
                        "progress": row["progress"],
                        "target": quest["target"],
                        "completed": row["progress"] >= int(quest["target"]),
                    }
                )

    return {"ok": True, "updated": updated, "season_id": season["id"]}


async def claim_quest(minecraft_name: str, quest_id: str) -> dict:
    season = await db.get_active_season()
    if not season:
        return {"ok": False, "error": "no_active_season"}

    player = await db.ensure_player(minecraft_name)
    quests = await db.list_quests(season["id"], active_only=True)
    quest = next((q for q in quests if q["id"] == quest_id), None)
    if not quest:
        return {"ok": False, "error": "quest_not_found"}

    progress = await db.get_quest_progress(minecraft_name, quest)
    if progress["claimed"]:
        return {"ok": False, "error": "already_claimed"}
    if int(progress["progress"]) < int(quest["target"]):
        return {"ok": False, "error": "not_complete", "progress": progress["progress"], "target": quest["target"]}

    progress["claimed"] = True
    await db.save_quest_progress(progress)

    base_xp = int(quest["xp_reward"])
    xp_gained = int(round(base_xp * (1 + PREMIUM_XP_BONUS))) if player["premium"] else base_xp

    state = await db.get_player_season(minecraft_name, season["id"])
    state = apply_xp(season, state, xp_gained)
    await db.save_player_season(state)

    view = await build_player_view(minecraft_name, season)
    return {
        "ok": True,
        "xp_gained": xp_gained,
        "xp_base": base_xp,
        "xp_bonus": xp_gained - base_xp,
        "view": view,
    }


async def claim_reward(minecraft_name: str, level: int, premium: bool) -> dict:
    season = await db.get_active_season()
    if not season:
        return {"ok": False, "error": "no_active_season"}

    player = await db.ensure_player(minecraft_name)
    state = await db.get_player_season(minecraft_name, season["id"])
    rewards = await db.list_rewards(season["id"])
    reward = next((r for r in rewards if r["level"] == level and r["premium"] == premium), None)
    if not reward:
        return {"ok": False, "error": "reward_not_found"}

    key = reward_claim_key(level, premium)
    claimed = list(state.get("claimed_rewards") or [])
    if key in claimed:
        return {"ok": False, "error": "already_claimed"}
    if level > int(state["level"]):
        return {"ok": False, "error": "level_locked"}
    if premium and not player["premium"]:
        return {"ok": False, "error": "premium_required"}

    claimed.append(key)
    state["claimed_rewards"] = claimed
    await db.save_player_season(state)

    grant_id = await db.enqueue_grant(
        minecraft_name,
        reward.get("grant_command") or "",
        reason=f"reward:{season['slug']}:L{level}:{'prem' if premium else 'free'}",
    )

    view = await build_player_view(minecraft_name, season)
    return {
        "ok": True,
        "reward": reward,
        "grant_command": db.render_command(reward.get("grant_command") or "", minecraft_name),
        "grant_id": grant_id,
        "view": view,
    }


async def set_premium(minecraft_name: str, premium: bool) -> dict:
    """Activate/deactivate Premium: LP groups, exclusive skins, level boost, XP bonus flag."""
    season = await db.get_active_season()
    player = await db.ensure_player(minecraft_name)
    was_premium = bool(player["premium"])
    await db.set_player_premium(minecraft_name, premium)

    grants: list[str] = []
    boosted_from = None
    boosted_to = None

    if premium and not was_premium:
        for cmd in PREMIUM_LP_COMMANDS:
            gid = await db.enqueue_grant(minecraft_name, cmd, reason="premium_activate")
            if gid:
                grants.append(gid)
        if season:
            state = await db.get_player_season(minecraft_name, season["id"])
            boosted_from = int(state["level"])
            if boosted_from < PREMIUM_LEVEL_BOOST:
                state["level"] = PREMIUM_LEVEL_BOOST
                # Fresh XP bar after boost feels fairer than keeping overflow XP.
                state["xp"] = 0
                await db.save_player_season(state)
                boosted_to = PREMIUM_LEVEL_BOOST
            else:
                boosted_to = boosted_from
    elif not premium and was_premium:
        for cmd in PREMIUM_REVOKE_COMMANDS:
            gid = await db.enqueue_grant(minecraft_name, cmd, reason="premium_deactivate")
            if gid:
                grants.append(gid)

    view = await build_player_view(minecraft_name, season)
    return {
        "ok": True,
        "view": view,
        "grants_queued": len(grants),
        "level_boost": {"from": boosted_from, "to": boosted_to} if boosted_from is not None else None,
        "benefits_active": bool(premium),
    }


async def admin_overview() -> dict:
    seasons = await db.list_seasons()
    active = await db.get_active_season()
    payload: dict[str, Any] = {
        "seasons": seasons,
        "active_season_id": active["id"] if active else None,
        "event_types": list(db.EVENT_TYPES),
        "recent_events": await db.recent_events(30),
    }
    if active:
        payload["quests"] = await db.list_quests(active["id"])
        payload["rewards"] = await db.list_rewards(active["id"])
    else:
        payload["quests"] = []
        payload["rewards"] = []
    return payload
