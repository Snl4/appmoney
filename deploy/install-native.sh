#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${APP_DIR}"

echo "==> Встановлення залежностей для budget-bot"

if ! command -v python3 >/dev/null 2>&1; then
  apt-get update
  apt-get install -y python3 python3-venv python3-pip
fi

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

mkdir -p data

SERVICE_FILE="/etc/systemd/system/budget-bot.service"
cp deploy/budget-bot-native.service "${SERVICE_FILE}"

systemctl daemon-reload
systemctl enable budget-bot
systemctl restart budget-bot

echo ""
echo "==> Готово!"
systemctl status budget-bot --no-pager || true
echo ""
echo "Логи: journalctl -u budget-bot -f"
