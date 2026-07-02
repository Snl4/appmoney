#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/budget-bot}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ "$(id -u)" -eq 0 ] && [ -z "${APP_DIR##/opt/*}" ]; then
  DEPLOY_DIR="${APP_DIR}"
else
  DEPLOY_DIR="${REPO_DIR}"
fi

echo "==> Деплой budget-bot -> ${DEPLOY_DIR}"

if [ "${DEPLOY_DIR}" != "${REPO_DIR}" ]; then
  mkdir -p "${DEPLOY_DIR}/data"
  rsync -av --delete \
    --exclude '.env' \
    --exclude 'data' \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '.venv' \
    "${REPO_DIR}/" "${DEPLOY_DIR}/"
fi

mkdir -p "${DEPLOY_DIR}/data"

if [ ! -f "${DEPLOY_DIR}/.env" ]; then
  cp "${DEPLOY_DIR}/.env.example" "${DEPLOY_DIR}/.env"
  echo ""
  echo "!!! Відредагуй ${DEPLOY_DIR}/.env — встав BOT_TOKEN від @BotFather"
  echo "    nano ${DEPLOY_DIR}/.env"
  echo ""
  exit 1
fi

cd "${DEPLOY_DIR}"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo "==> Запуск через Docker"
  docker compose down 2>/dev/null || true
  docker compose up -d --build
  echo ""
  docker compose ps
  echo ""
  echo "Логи: docker compose -f ${DEPLOY_DIR}/docker-compose.yml logs -f"
else
  echo "==> Docker не знайдено — нативний запуск (Python + systemd)"
  bash "${DEPLOY_DIR}/deploy/install-native.sh"
fi
