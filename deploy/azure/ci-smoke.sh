#!/usr/bin/env bash
# Runs only on the ephemeral GitHub runner, never against production state.
set -Eeuo pipefail
[[ ${GITHUB_ACTIONS:-} == true ]] || { echo 'This smoke script is for GitHub CI only.' >&2; exit 1; }
export API_IMAGE=yanshi-api:ci WEB_IMAGE=yanshi-web:ci
export DATA_VOLUME_NAME="yanshi-ci-${GITHUB_RUN_ID:?}-${GITHUB_RUN_ATTEMPT:?}"
dc() { sudo --preserve-env=API_IMAGE,WEB_IMAGE,DATA_VOLUME_NAME docker compose -p yanshi-ci -f deploy/azure/compose.yaml "$@"; }
cleanup() { dc logs --tail 60 api web; dc down; }
trap cleanup EXIT
sudo install -d -m 0700 /etc/yanshi
sudo tee /etc/yanshi/server.env >/dev/null <<'ENV'
ENVIRONMENT=production
DATABASE_URL=sqlite:////var/lib/yanshi/prod.sqlite
IMAGE_DIRECTORY=/var/lib/yanshi/uploads
JWT_SECRET=ci-only-not-a-real-secret-01234567890123456789012345678901234567890123456789
AI_KEY_ENC_SECRET=ci-only-not-a-real-key-98765432109876543210987654321098765432109876543210
PUBLIC_ORIGIN=https://duzhi.xin
CORS_ORIGINS=https://duzhi.xin
AUTH_PASSWORD_ONLY=true
REGISTRATION_OPEN=false
ADMIN_EMAIL=123456@qq.com
ADMIN_PASSWORD=CI-only-Password-2026!
IMAGE_STORAGE=qiniu
MAIL_CONSOLE=false
ENV
sudo chmod 0600 /etc/yanshi/server.env
dc config --quiet
docker build -f deploy/azure/Dockerfile.api -t "$API_IMAGE" .
docker build -f deploy/azure/Dockerfile.web -t "$WEB_IMAGE" .
dc run --rm --no-deps api python -m alembic upgrade head
dc run --rm --no-deps api python -m alembic check
initialization=$(dc run --rm --no-deps api python -m app.seed --quiet)
[[ $initialization != *'CI-only-Password-2026!'* ]]
dc run --rm --no-deps web -t
dc up -d --wait --wait-timeout 120
curl --fail --silent http://127.0.0.1:18080/health/ready
curl --fail --silent -D /tmp/yanshi-headers http://127.0.0.1:18080/rooms/1 -o /tmp/yanshi-index
grep -qi 'X-Content-Type-Options: nosniff' /tmp/yanshi-headers
grep -qi 'X-Frame-Options: DENY' /tmp/yanshi-headers
grep -qi 'Cache-Control: no-cache' /tmp/yanshi-headers
grep -q '<html' /tmp/yanshi-index
[[ $(curl --silent -o /dev/null -w '%{http_code}' http://127.0.0.1:18080/assets/missing-ci.js) == 404 ]]
curl --fail --silent -D /tmp/yanshi-sw-headers http://127.0.0.1:18080/sw.js -o /dev/null
grep -qi 'Cache-Control: no-cache' /tmp/yanshi-sw-headers
curl --fail --silent -D /tmp/yanshi-login-headers -H 'Content-Type: application/json' \
  -d '{"email":"123456@qq.com","password":"CI-only-Password-2026!"}' \
  http://127.0.0.1:18080/api/v1/auth/login > /tmp/yanshi-login.json
grep -qi 'Set-Cookie:.*HttpOnly' /tmp/yanshi-login-headers
grep -qi 'Set-Cookie:.*Secure' /tmp/yanshi-login-headers
[[ $(curl --silent -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' \
  -d '{"email":"123456@qq.com","scene":"login"}' http://127.0.0.1:18080/api/v1/auth/email-code) == 403 ]]
dc exec -T api python -c '
from app.config import Settings
from app.services.backup import create_backup,verify_and_restore
p=create_backup(Settings(),"/var/lib/yanshi/backups")
verify_and_restore(p,"/tmp/restore-ci")
print("Persistent volume backup and isolated restore passed")'
dc restart api
for attempt in $(seq 1 30); do
  if curl --fail --silent http://127.0.0.1:18080/health/ready; then break; fi
  sleep 2
done
curl --fail --silent http://127.0.0.1:18080/health/ready
echo 'Container migration, proxy, headers, authentication, restart and backup smoke passed'
