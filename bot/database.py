import json
import os
from pathlib import Path

import aiosqlite

DEFAULT_SETTINGS = {
    "advance_amount": 15000,
    "advance_day": 10,
    "salary_amount": 25000,
    "salary_day": 25,
    "transport_one_way": 25,
    "transport_trips_per_day": 2,
    "transport_work_days": [1, 2, 3, 4, 5],
    "transport_auto_enabled": True,
    "categories": ["Транспорт", "Їжа", "Комунальні", "Оренда", "Розваги", "Здоров'я", "Інше"],
}

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DB_PATH = DATA_DIR / "budget.db"


async def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                view_year INTEGER NOT NULL DEFAULT 2026,
                view_month INTEGER NOT NULL DEFAULT 0,
                settings TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT DEFAULT '',
                recurring INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS extra_income (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS transport_trips (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS month_overrides (
                user_id INTEGER NOT NULL,
                month_key TEXT NOT NULL,
                data TEXT NOT NULL,
                PRIMARY KEY (user_id, month_key)
            );
            """
        )
        await db.commit()


async def ensure_user(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
        if row:
            return {
                "user_id": row["user_id"],
                "view_year": row["view_year"],
                "view_month": row["view_month"],
                "settings": json.loads(row["settings"]),
            }

        from datetime import date

        today = date.today()
        settings = json.dumps(DEFAULT_SETTINGS, ensure_ascii=False)
        await db.execute(
            "INSERT INTO users (user_id, view_year, view_month, settings) VALUES (?, ?, ?, ?)",
            (user_id, today.year, today.month - 1, settings),
        )
        await db.commit()
        return {
            "user_id": user_id,
            "view_year": today.year,
            "view_month": today.month - 1,
            "settings": DEFAULT_SETTINGS.copy(),
        }


async def get_user(user_id: int) -> dict:
    return await ensure_user(user_id)


async def update_settings(user_id: int, settings: dict) -> None:
    await ensure_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET settings = ? WHERE user_id = ?",
            (json.dumps(settings, ensure_ascii=False), user_id),
        )
        await db.commit()


async def set_view_month(user_id: int, year: int, month: int) -> None:
    await ensure_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET view_year = ?, view_month = ? WHERE user_id = ?",
            (year, month, user_id),
        )
        await db.commit()


async def get_month_override(user_id: int, month_key: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT data FROM month_overrides WHERE user_id = ? AND month_key = ?",
            (user_id, month_key),
        ) as cur:
            row = await cur.fetchone()
    return json.loads(row[0]) if row else {}


async def set_month_override(user_id: int, month_key: str, patch: dict) -> None:
    current = await get_month_override(user_id, month_key)
    current.update(patch)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO month_overrides (user_id, month_key, data)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, month_key) DO UPDATE SET data = excluded.data
            """,
            (user_id, month_key, json.dumps(current, ensure_ascii=False)),
        )
        await db.commit()


async def add_expense(user_id: int, item: dict) -> None:
    await ensure_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO expenses (id, user_id, date, amount, category, description, recurring)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["id"], user_id, item["date"], item["amount"],
                item["category"], item.get("description", ""),
                1 if item.get("recurring") else 0,
            ),
        )
        await db.commit()


async def delete_expense(user_id: int, expense_id: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM expenses WHERE user_id = ? AND id = ?", (user_id, expense_id))
        await db.commit()


async def list_expenses(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC", (user_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [
        {
            "id": r["id"], "date": r["date"], "amount": r["amount"],
            "category": r["category"], "description": r["description"],
            "recurring": bool(r["recurring"]),
        }
        for r in rows
    ]


async def add_extra_income(user_id: int, item: dict) -> None:
    await ensure_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO extra_income (id, user_id, date, amount, description) VALUES (?, ?, ?, ?, ?)",
            (item["id"], user_id, item["date"], item["amount"], item.get("description", "")),
        )
        await db.commit()


async def list_extra_income(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM extra_income WHERE user_id = ? ORDER BY date DESC", (user_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [
        {"id": r["id"], "date": r["date"], "amount": r["amount"], "description": r["description"]}
        for r in rows
    ]


async def add_transport_trip(user_id: int, item: dict) -> None:
    await ensure_user(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO transport_trips (id, user_id, date, amount, description) VALUES (?, ?, ?, ?, ?)",
            (item["id"], user_id, item["date"], item["amount"], item.get("description", "")),
        )
        await db.commit()


async def list_transport_trips(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM transport_trips WHERE user_id = ? ORDER BY date DESC", (user_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [
        {"id": r["id"], "date": r["date"], "amount": r["amount"], "description": r["description"]}
        for r in rows
    ]
