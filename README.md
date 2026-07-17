# RateYou

Telegram-бот для оценки анкет с оплатой через Telegram Stars.

## Деплой

CI/CD настроен через GitHub Actions:

- [.github/workflows/ci.yml](.github/workflows/ci.yml) — проверки на каждый PR (ruff + mypy + pytest).
- [.github/workflows/cd.yml](.github/workflows/cd.yml) — на push в `main`: проверки → сборка образа в GHCR (`ghcr.io/vasiliikletkin/rateyou:latest`) → деплой по SSH.
- [.github/workflows/checks.yml](.github/workflows/checks.yml) — переиспользуемые проверки, общие для CI и CD.

Сервер тянет готовый образ и поднимает стек через [docker-compose.prod.yml](docker-compose.prod.yml); миграции прогоняет сервис `migrate` автоматически.

### Настройка GitHub (Settings → Environments → `prod`)

**Variables:** `SSH_HOST`, `SSH_USER`, `SSH_PORT` (опц., дефолт 22), `DEPLOY_PATH`.
**Secrets:** `SSH_SECRET_KEY` (приватный SSH-ключ в base64), `GHCR_SECRET_TOKEN` (PAT с `read:packages`, если образ приватный).

## TODO

- [ ] **Отдельный пользователь для деплоя.** Сейчас GitHub Actions ходит по SSH под `root`. Завести непривилегированного пользователя (напр. `deploy`), добавить его в группу `docker`, положить публичный ключ в его `~/.ssh/authorized_keys` и переключить переменную `SSH_USER` на него.
- [ ] **Откат по тегу.** Имя образа зашито как `:latest` в [docker-compose.prod.yml](docker-compose.prod.yml) — для отката на конкретный `:sha-<commit>` нужен ручной правке тега. При необходимости вынести тег в переменную.
