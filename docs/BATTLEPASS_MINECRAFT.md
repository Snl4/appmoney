# Як Battle Pass дізнається, що гравець виконав квест

Коротко: **сайт сам Minecraft не слухає**. На сервері стоїть плагін, який ловить ігрові дії й шле їх на API. API оновлює прогрес квестів. Гравець на сайті лише забирає XP / нагороди.

```
┌────────────────────┐     POST /api/battlepass/events      ┌────────────────────┐
│  Paper/Spigot      │ ───────────────────────────────────► │  Battle Pass API   │
│  CapyBattlePass    │   X-API-Key: MINECRAFT_API_KEY       │  (цей репозиторій) │
│  plugin            │                                      └─────────┬──────────┘
└─────────┬──────────┘                                                │
          │ слухає Bukkit events                                      │ SQLite
          │ PlayerMove, EntityDeath,                                  ▼
          │ CraftItem, BlockPlace,                          quest_progress /
          │ AsyncPlayerChat, ...                            player_season
                                                               │
                                                               ▼
                                                    GET /api/battlepass/view
                                                    (веб-сторінка гравця)
```

## 1. Адмін створює сезон і квести

UI: `/battlepass/admin` (ключ `BATTLEPASS_ADMIN_KEY`).

Квест прив’язаний до **типу події**, наприклад:

| Квест | `event_type` | `target` |
|------|--------------|----------|
| Пройди 2000 блоків | `walk_blocks` | 2000 |
| Убий 20 мобів | `kill_mobs` | 20 |
| Скрафти 16 предметів | `craft_items` | 16 |
| Постав 500 блоків | `place_blocks` | 500 |
| 10 повідомлень у чаті | `chat_messages` | 10 |
| 3 біоми | `visit_biome` | 3 |
| 5 угод на ринку | `market_trades` | 5 |

Повний список: `GET /api/battlepass/event-types`.

## 2. Minecraft-плагін шле прогрес

```http
POST /api/battlepass/events
X-API-Key: <MINECRAFT_API_KEY>
Content-Type: application/json

{
  "events": [
    { "player": "Steve", "type": "walk_blocks", "amount": 12, "meta": {} },
    { "player": "Steve", "type": "kill_mobs", "amount": 1, "meta": { "entity": "ZOMBIE" } },
    { "player": "Steve", "type": "visit_biome", "amount": 1, "meta": { "biome": "plains" } }
  ]
}
```

API знаходить активні квести з таким `event_type` і додає `amount` до прогресу (з урахуванням `meta_filter`).

## 3. Що має робити плагін (мінімум)

Рекомендований стек: **Paper 1.21+**, окремий плагін `CapyBattlePass`.

1. Слухати івенти Bukkit / Paper.
2. Батчити зміни (наприклад раз на 5–10 секунд або при logout), щоб не спамити HTTP.
3. Для `walk_blocks` рахувати дистанцію з `PlayerMoveEvent` (тільки зміна блока).
4. Для `visit_biome` — слати `amount: 1` лише при **першому** заході в біом за період.
5. Для економіки (`market_trades`) — хук у ваш плагін ринку / при кастомному івенті.
6. Після claim нагороди на сайті можна окремо забирати `grant_command` і виконувати на сервері (через чергу або polling).

Псевдокод:

```java
@EventHandler
public void onDeath(EntityDeathEvent e) {
  if (!(e.getEntity().getKiller() instanceof Player p)) return;
  queue.add(new BpEvent(p.getName(), "kill_mobs", 1, Map.of()));
}
```

## 4. Гравець на сайті

1. Відкриває `/battlepass`, вводить свій Minecraft нік.
2. Бачить прогрес квестів (вже оновлений плагіном).
3. Тисне **Забрати** → отримує XP → відкриваються рівні нагород.

Симуляція без плагіна: в адмінці блок «Симуляція Minecraft-події» або

```bash
curl -X POST http://127.0.0.1:8765/api/battlepass/events \
  -H "X-API-Key: capy-mc-dev" \
  -H "Content-Type: application/json" \
  -d '{"player":"Steve","type":"craft_items","amount":5}'
```

## 5. Новий Battle Pass

1. Адмінка → **Новий сезон** (позначити активним).
2. Додати нагороди по рівнях (free / premium).
3. Додати квести з потрібними `event_type`.
4. Плагін нічого особливого міняти не треба — він лише шле події; квести читаються з активного сезону на API.

## Ключі (.env)

```
BATTLEPASS_ADMIN_KEY=capy-admin-dev
MINECRAFT_API_KEY=capy-mc-dev
```

На проді поставте довгі секрети й віддавайте Minecraft API лише з IP ігрового сервера (firewall / reverse proxy).
