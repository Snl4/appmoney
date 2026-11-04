"""SQLite storage for Battle Pass seasons, quests, rewards and player progress."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from bot.database import DATA_DIR

DB_PATH = Path(os.getenv("BATTLEPASS_DB", str(DATA_DIR / "battlepass.db")))

EVENT_TYPES = (
    "walk_blocks",
    "kill_mobs",
    "craft_items",
    "place_blocks",
    "break_blocks",
    "chat_messages",
    "visit_biome",
    "market_trades",
    "login_day",
    "play_minutes",
    "custom",
)


def new_id(prefix: str = "") -> str:
    raw = uuid.uuid4().hex[:12]
    return f"{prefix}{raw}" if prefix else raw


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def period_key(resets: str, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    if resets == "daily":
        return now.strftime("%Y-%m-%d")
    if resets == "weekly":
        iso = now.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    return "season"


async def init_battlepass_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS seasons (
                id TEXT PRIMARY KEY,
                number INTEGER NOT NULL,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                starts_at TEXT NOT NULL,
                ends_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 0,
                xp_base INTEGER NOT NULL DEFAULT 2200,
                xp_growth REAL NOT NULL DEFAULT 1.08,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rewards (
                id TEXT PRIMARY KEY,
                season_id TEXT NOT NULL,
                level INTEGER NOT NULL,
                name TEXT NOT NULL,
                icon TEXT NOT NULL DEFAULT 'fa-gift',
                premium INTEGER NOT NULL DEFAULT 0,
                grant_command TEXT NOT NULL DEFAULT '',
                UNIQUE(season_id, level, premium),
                FOREIGN KEY(season_id) REFERENCES seasons(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS quests (
                id TEXT PRIMARY KEY,
                season_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                icon TEXT NOT NULL DEFAULT 'fa-scroll',
                event_type TEXT NOT NULL,
                target INTEGER NOT NULL,
                xp_reward INTEGER NOT NULL,
                resets TEXT NOT NULL DEFAULT 'never',
                meta_filter TEXT NOT NULL DEFAULT '{}',
                active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(season_id) REFERENCES seasons(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS players (
                minecraft_name TEXT PRIMARY KEY COLLATE NOCASE,
                display_name TEXT NOT NULL DEFAULT '',
                premium INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS player_season (
                minecraft_name TEXT NOT NULL COLLATE NOCASE,
                season_id TEXT NOT NULL,
                xp INTEGER NOT NULL DEFAULT 0,
                level INTEGER NOT NULL DEFAULT 1,
                claimed_rewards TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (minecraft_name, season_id),
                FOREIGN KEY(season_id) REFERENCES seasons(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS quest_progress (
                minecraft_name TEXT NOT NULL COLLATE NOCASE,
                quest_id TEXT NOT NULL,
                period_key TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                claimed INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (minecraft_name, quest_id, period_key),
                FOREIGN KEY(quest_id) REFERENCES quests(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS event_log (
                id TEXT PRIMARY KEY,
                minecraft_name TEXT NOT NULL COLLATE NOCASE,
                event_type TEXT NOT NULL,
                amount INTEGER NOT NULL,
                meta TEXT NOT NULL DEFAULT '{}',
                source TEXT NOT NULL DEFAULT 'minecraft',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_quests_season ON quests(season_id, active);
            CREATE INDEX IF NOT EXISTS idx_rewards_season ON rewards(season_id, level);
            CREATE INDEX IF NOT EXISTS idx_events_player ON event_log(minecraft_name, created_at);
            """
        )
        await db.commit()


async def _fetchall(db: aiosqlite.Connection, sql: str, params: tuple = ()) -> list[dict]:
    db.row_factory = aiosqlite.Row
    async with db.execute(sql, params) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def _fetchone(db: aiosqlite.Connection, sql: str, params: tuple = ()) -> dict | None:
    rows = await _fetchall(db, sql, params)
    return rows[0] if rows else None


async def list_seasons() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        return await _fetchall(db, "SELECT * FROM seasons ORDER BY number DESC")


async def get_season(season_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        return await _fetchone(db, "SELECT * FROM seasons WHERE id = ?", (season_id,))


async def get_active_season() -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        return await _fetchone(db, "SELECT * FROM seasons WHERE active = 1 ORDER BY number DESC LIMIT 1")


async def create_season(payload: dict) -> dict:
    season = {
        "id": new_id("s_"),
        "number": int(payload["number"]),
        "name": payload["name"].strip(),
        "slug": payload.get("slug") or f"season-{payload['number']}",
        "description": payload.get("description", ""),
        "starts_at": payload["starts_at"],
        "ends_at": payload["ends_at"],
        "active": 1 if payload.get("active") else 0,
        "xp_base": int(payload.get("xp_base", 2200)),
        "xp_growth": float(payload.get("xp_growth", 1.08)),
        "created_at": utc_now(),
    }
    async with aiosqlite.connect(DB_PATH) as db:
        if season["active"]:
            await db.execute("UPDATE seasons SET active = 0")
        await db.execute(
            """
            INSERT INTO seasons
            (id, number, name, slug, description, starts_at, ends_at, active, xp_base, xp_growth, created_at)
            VALUES (:id, :number, :name, :slug, :description, :starts_at, :ends_at, :active, :xp_base, :xp_growth, :created_at)
            """,
            season,
        )
        await db.commit()
    return season


async def update_season(season_id: str, patch: dict) -> dict | None:
    current = await get_season(season_id)
    if not current:
        return None
    allowed = ("name", "description", "starts_at", "ends_at", "active", "xp_base", "xp_growth", "number", "slug")
    for key in allowed:
        if key in patch:
            current[key] = patch[key]
    current["active"] = 1 if current.get("active") else 0
    async with aiosqlite.connect(DB_PATH) as db:
        if current["active"]:
            await db.execute("UPDATE seasons SET active = 0 WHERE id != ?", (season_id,))
        await db.execute(
            """
            UPDATE seasons SET
              number=?, name=?, slug=?, description=?, starts_at=?, ends_at=?,
              active=?, xp_base=?, xp_growth=?
            WHERE id=?
            """,
            (
                int(current["number"]),
                current["name"],
                current["slug"],
                current["description"],
                current["starts_at"],
                current["ends_at"],
                int(current["active"]),
                int(current["xp_base"]),
                float(current["xp_growth"]),
                season_id,
            ),
        )
        await db.commit()
    return await get_season(season_id)


async def list_rewards(season_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await _fetchall(
            db,
            "SELECT * FROM rewards WHERE season_id = ? ORDER BY level ASC, premium ASC",
            (season_id,),
        )
    for row in rows:
        row["premium"] = bool(row["premium"])
    return rows


async def upsert_reward(payload: dict) -> dict:
    reward = {
        "id": payload.get("id") or new_id("r_"),
        "season_id": payload["season_id"],
        "level": int(payload["level"]),
        "name": payload["name"].strip(),
        "icon": payload.get("icon") or "fa-gift",
        "premium": 1 if payload.get("premium") else 0,
        "grant_command": payload.get("grant_command") or "",
    }
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO rewards (id, season_id, level, name, icon, premium, grant_command)
            VALUES (:id, :season_id, :level, :name, :icon, :premium, :grant_command)
            ON CONFLICT(season_id, level, premium) DO UPDATE SET
              name=excluded.name,
              icon=excluded.icon,
              grant_command=excluded.grant_command,
              id=rewards.id
            """,
            reward,
        )
        row = await _fetchone(
            db,
            "SELECT * FROM rewards WHERE season_id=? AND level=? AND premium=?",
            (reward["season_id"], reward["level"], reward["premium"]),
        )
        await db.commit()
    assert row
    row["premium"] = bool(row["premium"])
    return row


async def delete_reward(reward_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM rewards WHERE id = ?", (reward_id,))
        await db.commit()
        return cur.rowcount > 0


async def list_quests(season_id: str, active_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM quests WHERE season_id = ?"
    params: list[Any] = [season_id]
    if active_only:
        sql += " AND active = 1"
    sql += " ORDER BY kind ASC, sort_order ASC, title ASC"
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await _fetchall(db, sql, tuple(params))
    for row in rows:
        row["active"] = bool(row["active"])
        row["meta_filter"] = json.loads(row["meta_filter"] or "{}")
    return rows


async def create_quest(payload: dict) -> dict:
    event_type = payload["event_type"]
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unknown event_type: {event_type}")
    quest = {
        "id": payload.get("id") or new_id("q_"),
        "season_id": payload["season_id"],
        "kind": payload.get("kind") or "daily",
        "title": payload["title"].strip(),
        "description": payload.get("description", ""),
        "icon": payload.get("icon") or "fa-scroll",
        "event_type": event_type,
        "target": int(payload["target"]),
        "xp_reward": int(payload["xp_reward"]),
        "resets": payload.get("resets") or ("daily" if payload.get("kind") == "daily" else "weekly" if payload.get("kind") == "weekly" else "never"),
        "meta_filter": json.dumps(payload.get("meta_filter") or {}, ensure_ascii=False),
        "active": 1 if payload.get("active", True) else 0,
        "sort_order": int(payload.get("sort_order", 0)),
    }
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO quests
            (id, season_id, kind, title, description, icon, event_type, target, xp_reward, resets, meta_filter, active, sort_order)
            VALUES
            (:id, :season_id, :kind, :title, :description, :icon, :event_type, :target, :xp_reward, :resets, :meta_filter, :active, :sort_order)
            """,
            quest,
        )
        await db.commit()
    quest["active"] = bool(quest["active"])
    quest["meta_filter"] = json.loads(quest["meta_filter"])
    return quest


async def update_quest(quest_id: str, patch: dict) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        row = await _fetchone(db, "SELECT * FROM quests WHERE id = ?", (quest_id,))
        if not row:
            return None
        fields = {
            "kind": patch.get("kind", row["kind"]),
            "title": patch.get("title", row["title"]),
            "description": patch.get("description", row["description"]),
            "icon": patch.get("icon", row["icon"]),
            "event_type": patch.get("event_type", row["event_type"]),
            "target": int(patch.get("target", row["target"])),
            "xp_reward": int(patch.get("xp_reward", row["xp_reward"])),
            "resets": patch.get("resets", row["resets"]),
            "meta_filter": json.dumps(patch["meta_filter"], ensure_ascii=False)
            if "meta_filter" in patch
            else row["meta_filter"],
            "active": 1 if patch.get("active", row["active"]) else 0,
            "sort_order": int(patch.get("sort_order", row["sort_order"])),
        }
        if fields["event_type"] not in EVENT_TYPES:
            raise ValueError(f"Unknown event_type: {fields['event_type']}")
        await db.execute(
            """
            UPDATE quests SET
              kind=?, title=?, description=?, icon=?, event_type=?, target=?,
              xp_reward=?, resets=?, meta_filter=?, active=?, sort_order=?
            WHERE id=?
            """,
            (
                fields["kind"],
                fields["title"],
                fields["description"],
                fields["icon"],
                fields["event_type"],
                fields["target"],
                fields["xp_reward"],
                fields["resets"],
                fields["meta_filter"],
                fields["active"],
                fields["sort_order"],
                quest_id,
            ),
        )
        await db.commit()
    quests = await list_quests(row["season_id"])
    return next((q for q in quests if q["id"] == quest_id), None)


async def delete_quest(quest_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM quests WHERE id = ?", (quest_id,))
        await db.commit()
        return cur.rowcount > 0


async def ensure_player(minecraft_name: str) -> dict:
    name = minecraft_name.strip()
    async with aiosqlite.connect(DB_PATH) as db:
        row = await _fetchone(db, "SELECT * FROM players WHERE minecraft_name = ?", (name,))
        if row:
            row["premium"] = bool(row["premium"])
            return row
        player = {
            "minecraft_name": name,
            "display_name": name,
            "premium": 0,
            "created_at": utc_now(),
        }
        await db.execute(
            "INSERT INTO players (minecraft_name, display_name, premium, created_at) VALUES (?, ?, ?, ?)",
            (player["minecraft_name"], player["display_name"], 0, player["created_at"]),
        )
        await db.commit()
        player["premium"] = False
        return player


async def set_player_premium(minecraft_name: str, premium: bool) -> dict:
    await ensure_player(minecraft_name)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE players SET premium = ? WHERE minecraft_name = ?",
            (1 if premium else 0, minecraft_name),
        )
        await db.commit()
    return await ensure_player(minecraft_name)


async def get_player_season(minecraft_name: str, season_id: str) -> dict:
    await ensure_player(minecraft_name)
    async with aiosqlite.connect(DB_PATH) as db:
        row = await _fetchone(
            db,
            "SELECT * FROM player_season WHERE minecraft_name = ? AND season_id = ?",
            (minecraft_name, season_id),
        )
        if row:
            row["claimed_rewards"] = json.loads(row["claimed_rewards"] or "[]")
            return row
        data = {
            "minecraft_name": minecraft_name,
            "season_id": season_id,
            "xp": 0,
            "level": 1,
            "claimed_rewards": "[]",
            "updated_at": utc_now(),
        }
        await db.execute(
            """
            INSERT INTO player_season (minecraft_name, season_id, xp, level, claimed_rewards, updated_at)
            VALUES (:minecraft_name, :season_id, :xp, :level, :claimed_rewards, :updated_at)
            """,
            data,
        )
        await db.commit()
        data["claimed_rewards"] = []
        return data


async def save_player_season(state: dict) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE player_season
            SET xp=?, level=?, claimed_rewards=?, updated_at=?
            WHERE minecraft_name=? AND season_id=?
            """,
            (
                int(state["xp"]),
                int(state["level"]),
                json.dumps(state.get("claimed_rewards") or [], ensure_ascii=False),
                utc_now(),
                state["minecraft_name"],
                state["season_id"],
            ),
        )
        await db.commit()


async def get_quest_progress(minecraft_name: str, quest: dict) -> dict:
    key = period_key(quest["resets"])
    async with aiosqlite.connect(DB_PATH) as db:
        row = await _fetchone(
            db,
            """
            SELECT * FROM quest_progress
            WHERE minecraft_name=? AND quest_id=? AND period_key=?
            """,
            (minecraft_name, quest["id"], key),
        )
        if row:
            row["claimed"] = bool(row["claimed"])
            return row
        data = {
            "minecraft_name": minecraft_name,
            "quest_id": quest["id"],
            "period_key": key,
            "progress": 0,
            "claimed": 0,
            "updated_at": utc_now(),
        }
        await db.execute(
            """
            INSERT INTO quest_progress
            (minecraft_name, quest_id, period_key, progress, claimed, updated_at)
            VALUES (:minecraft_name, :quest_id, :period_key, :progress, :claimed, :updated_at)
            """,
            data,
        )
        await db.commit()
        data["claimed"] = False
        return data


async def save_quest_progress(row: dict) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE quest_progress
            SET progress=?, claimed=?, updated_at=?
            WHERE minecraft_name=? AND quest_id=? AND period_key=?
            """,
            (
                int(row["progress"]),
                1 if row.get("claimed") else 0,
                utc_now(),
                row["minecraft_name"],
                row["quest_id"],
                row["period_key"],
            ),
        )
        await db.commit()


async def log_event(minecraft_name: str, event_type: str, amount: int, meta: dict, source: str) -> str:
    event_id = new_id("e_")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO event_log (id, minecraft_name, event_type, amount, meta, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                minecraft_name,
                event_type,
                int(amount),
                json.dumps(meta or {}, ensure_ascii=False),
                source,
                utc_now(),
            ),
        )
        await db.commit()
    return event_id


async def recent_events(limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await _fetchall(
            db,
            "SELECT * FROM event_log ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
    for row in rows:
        row["meta"] = json.loads(row["meta"] or "{}")
    return rows


async def seed_demo_if_empty() -> None:
    seasons = await list_seasons()
    if seasons:
        return

    from datetime import timedelta

    now = datetime.now(timezone.utc)
    season = await create_season(
        {
            "number": 3,
            "name": "Золота Долина",
            "slug": "golden-valley",
            "description": "Сезонний Battle Pass Долини Капібар",
            "starts_at": (now - timedelta(days=12)).replace(microsecond=0).isoformat(),
            "ends_at": (now + timedelta(days=18, hours=6)).replace(microsecond=0).isoformat(),
            "active": True,
            "xp_base": 2200,
            "xp_growth": 1.08,
        }
    )

    demo_rewards = [
        (1, "50 монет", "fa-coins", False),
        (2, "Ключ скрині", "fa-key", True),
        (3, "Шолом мандрівника", "fa-helmet-safety", False),
        (4, "XP буст 1г", "fa-bolt", True),
        (5, "Емоут «Чіл»", "fa-face-smile", False),
        (6, "Скін плаща", "fa-shirt", True),
        (7, "Баннер Долини", "fa-flag", False),
        (8, "200 монет", "fa-sack-dollar", True),
        (9, "Фейєрверк", "fa-fire", False),
        (10, "Титул «Слідопит»", "fa-certificate", True),
        (11, "Набір інструментів", "fa-toolbox", False),
        (12, "Пегас-маунт скін", "fa-horse", True),
        (13, "Рідкісний кейс", "fa-box-open", False),
        (14, "Аура золота", "fa-sun", True),
        (15, "Корона сезону", "fa-crown", True),
    ]
    for level, name, icon, premium in demo_rewards:
        await upsert_reward(
            {
                "season_id": season["id"],
                "level": level,
                "name": name,
                "icon": icon,
                "premium": premium,
                "grant_command": f"bp grant %player% season3_lvl{level}{'_prem' if premium else ''}",
            }
        )

    demo_quests = [
        {
            "kind": "daily",
            "title": "Прогулянка долиною",
            "description": "Пройди 2 000 блоків пішки",
            "icon": "fa-person-walking",
            "event_type": "walk_blocks",
            "target": 2000,
            "xp_reward": 120,
            "resets": "daily",
        },
        {
            "kind": "daily",
            "title": "Ремісник дня",
            "description": "Скрафти 16 предметів",
            "icon": "fa-hammer",
            "event_type": "craft_items",
            "target": 16,
            "xp_reward": 150,
            "resets": "daily",
        },
        {
            "kind": "daily",
            "title": "Голос громади",
            "description": "Напиши 10 повідомлень у чаті",
            "icon": "fa-comments",
            "event_type": "chat_messages",
            "target": 10,
            "xp_reward": 80,
            "resets": "daily",
        },
        {
            "kind": "daily",
            "title": "Полювання на зомбі",
            "description": "Убий 20 ворожих мобів",
            "icon": "fa-skull",
            "event_type": "kill_mobs",
            "target": 20,
            "xp_reward": 180,
            "resets": "daily",
        },
        {
            "kind": "weekly",
            "title": "Будівничий тижня",
            "description": "Постав 500 блоків",
            "icon": "fa-cube",
            "event_type": "place_blocks",
            "target": 500,
            "xp_reward": 600,
            "resets": "weekly",
        },
        {
            "kind": "weekly",
            "title": "Економіка Долини",
            "description": "Зроби 5 угод на ринку",
            "icon": "fa-handshake",
            "event_type": "market_trades",
            "target": 5,
            "xp_reward": 450,
            "resets": "weekly",
        },
        {
            "kind": "weekly",
            "title": "Дослідник країв",
            "description": "Відвідай 3 різні біоми",
            "icon": "fa-compass",
            "event_type": "visit_biome",
            "target": 3,
            "xp_reward": 500,
            "resets": "weekly",
        },
    ]
    for i, q in enumerate(demo_quests):
        q["season_id"] = season["id"]
        q["sort_order"] = i
        q["active"] = True
        await create_quest(q)

    # Demo player with partial progress so UI is not empty.
    player = "Steve"
    await ensure_player(player)
    state = await get_player_season(player, season["id"])
    state["level"] = 7
    state["xp"] = 1840
    state["claimed_rewards"] = [
        "1:0", "2:1", "3:0", "4:1", "5:0", "6:1",
    ]
    await save_player_season(state)

    quests = await list_quests(season["id"], active_only=True)
    by_title = {q["title"]: q for q in quests}
    presets = {
        "Прогулянка долиною": 1480,
        "Ремісник дня": 16,
        "Голос громади": 4,
        "Полювання на зомбі": 20,
        "Будівничий тижня": 312,
        "Економіка Долини": 2,
        "Дослідник країв": 3,
    }
    for title, progress in presets.items():
        quest = by_title[title]
        row = await get_quest_progress(player, quest)
        row["progress"] = progress
        if title == "Полювання на зомбі":
            row["claimed"] = True
            # Already claimed XP reflected roughly in seeded level/xp.
        await save_quest_progress(row)
