# LuckPerms + Premium Pass

## Що реально працює в API

| Бонус з банера | Статус | Як |
|---|---|---|
| Подвійні нагороди | ✅ | Free + Premium трек на кожному рівні |
| Ексклюзивні скіни | ✅ через LP | При Premium: `bp.skin.premium`, `bp.cosmetic.exclusive`; нагороди дають `bp.skin.*` |
| +20% XP | ✅ | При claim квесту XP × 1.20 якщо `premium=1` |
| Буст до рівня 5 | ✅ | При першій активації Premium рівень піднімається мінімум до 5 |

Раніше в банері це був лише текст. Тепер бонуси в `bot/battlepass_logic.py`.

## Потік LuckPerms

```
Сайт / API                     Minecraft plugin                 LuckPerms
─────────                      ─────────────────                ─────────
Premium ON  ──queue──► pending_grants
Claim reward ──queue──► pending_grants
                       ◄── GET /api/battlepass/grants ──
                       dispatchConsoleCommand(cmd)
                       ── POST /api/battlepass/grants/ack ──►
                                                            group bp.premium
                                                            permissions bp.skin.*
```

### Команди при активації Premium

```
lp user %player% parent add bp.premium
lp user %player% permission set bp.skin.premium true
lp user %player% permission set bp.cosmetic.exclusive true
```

### Приклад нагород (seed)

```
lp user %player% permission set bp.skin.cloak.gold true
lp user %player% meta setsuffix 100 " &6Слідопит"
lp user %player% parent add bp.season3.champion
```

## API для плагіна

```http
GET /api/battlepass/grants?player=Steve
X-API-Key: <MINECRAFT_API_KEY>
```

```http
POST /api/battlepass/grants/ack
X-API-Key: <MINECRAFT_API_KEY>
{"ids":["g_abc123"]}
```

Також `POST /api/battlepass/events` повертає `pending_grants` у відповіді — можна забирати команди одразу після івентів.

## Налаштування LuckPerms на сервері

1. Створити групу:

```
/lp creategroup bp.premium
/lp group bp.premium meta setprefix 50 "&6[BP] "
/lp group bp.premium permission set bp.skin.premium true
/lp group bp.premium permission set bp.cosmetic.exclusive true
```

2. Скін-плагін / cosmetics мають перевіряти права `bp.skin.*` / `bp.cosmetic.*`.

3. Плагін Battle Pass кожні N секунд (або на join) тягне `/grants` і виконує команди від консолі.

## Тест без плагіна

```bash
# активувати premium
curl -X POST http://127.0.0.1:8765/api/battlepass/premium \
  -H 'Content-Type: application/json' \
  -d '{"player":"Steve","premium":true}'

# подивитись чергу LP-команд
curl -H 'X-API-Key: capy-mc-dev' \
  'http://127.0.0.1:8765/api/battlepass/grants?player=Steve'
```
