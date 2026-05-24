# Деплой RateYou на VPS

Пошаговая инструкция: от пустого VPS до работающего бота. Конфигурация —
**polling, без webhook и домена** (MVP-вариант). Postgres и Redis живут
в docker-compose рядом с ботом. Время на всё — ~30 минут.

> Когда дорастёшь до webhook + домена — см. блок [Переключение на webhook](#переключение-на-webhook) в конце.

---

## 1. Что нужно подготовить заранее

1. **Сервер.** Любой VPS с Ubuntu 24.04 LTS, минимум 1 ГБ RAM, 20 ГБ диска.
   Рекомендуемый минимум — Hetzner Cloud CX22 (~€4.5/мес) или DigitalOcean
   Basic ($6).
2. **Токен бота.** [@BotFather](https://t.me/BotFather) → `/newbot`
   (для прода создай **отдельного** бота, не используй dev-токен).
3. **Sentry-проект** (опционально). DSN уже есть в `.env.example`, можно
   создать новый проект под прод и поменять DSN.
4. **SSH-ключ** на твоей рабочей машине: `ssh-keygen -t ed25519`, добавить
   на VPS при создании.

---

## 2. Базовая настройка сервера

Все команды — от `root` через `ssh root@<server-ip>`, пока не создадим
deploy-юзера.

```bash
# Обновление и базовые утилиты
apt update && apt upgrade -y
apt install -y git ufw curl

# Swap 2GB (важно при 1GB RAM — Docker build умеет жрать память)
fallocate -l 2G /swapfile && chmod 600 /swapfile
mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# Firewall: пускаем только SSH (80/443 откроем, когда дойдём до webhook)
ufw allow OpenSSH
ufw --force enable

# Непривилегированный юзер для деплоя
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh
cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys
```

### Установка Docker

```bash
# Официальный скрипт
curl -fsSL https://get.docker.com | sh
usermod -aG docker deploy

# Проверка
docker --version
docker compose version
```

Дальше всё под `deploy`:

```bash
exit                              # выйти из root
ssh deploy@<server-ip>
```

---

## 3. Клонирование и .env

```bash
cd ~
git clone https://github.com/<your-org>/RateYou.git
cd RateYou
cp .env.example .env
nano .env
```

Минимальный `.env` для прода:

```ini
ENVIRONMENT=prod
LOG_LEVEL=INFO

BOT_TOKEN=<токен из @BotFather>
BOT_USE_WEBHOOK=false             # polling для MVP

# Сильные пароли — НЕ rateyou:
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=rateyou
POSTGRES_USER=rateyou
POSTGRES_PASSWORD=<openssl rand -base64 32>

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

ADMIN_USERNAME=admin
ADMIN_PASSWORD=<openssl rand -base64 24>
ADMIN_SECRET_KEY=<openssl rand -hex 32>

SENTRY_DSN=<DSN прод-проекта>
SENTRY_TRACES_SAMPLE_RATE=0.1
```

Сгенерировать пароли можно тут же:
```bash
openssl rand -base64 32   # для POSTGRES_PASSWORD
openssl rand -base64 24   # для ADMIN_PASSWORD
openssl rand -hex 32      # для ADMIN_SECRET_KEY
```

`chmod 600 .env` — чтобы только владелец читал.

---

## 4. Закрыть порты Postgres и Redis от внешнего мира

В текущем [docker-compose.yml](../docker-compose.yml) postgres и redis
публикуют свои порты на хосте (`5432`, `6379`). В проде это значит, что
любой в интернете может попробовать подобрать к ним пароль — даже за UFW
Docker сам открывает порты в `iptables` минуя UFW.

Создай `docker-compose.prod.yml` рядом с основным:

```yaml
services:
  postgres:
    ports: !reset []     # сбрасываем публикацию порта 5432
  redis:
    ports: !reset []     # сбрасываем 6379

  admin:
    ports: !reset
      - "127.0.0.1:8000:8000"   # админка только на localhost
```

`!reset []` (Compose 2.24+) полностью убирает `ports:` из базового
файла. Postgres и Redis остаются доступны только внутри docker-сети
(оттуда их видят bot/admin/migrate).

Админка теперь доступна **только через SSH-туннель**:
```bash
ssh -L 8000:localhost:8000 deploy@<server-ip>
# на ноуте открыть http://localhost:8000
```

Дальше во всех командах подключай оба файла:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Чтобы не писать длинное каждый раз — добавь в `~/.bashrc` на сервере:
```bash
export COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml
```

---

## 5. Первый запуск

```bash
docker compose up -d --build
```

Compose:
1. Соберёт образ.
2. Поднимет `postgres` → дождётся healthcheck.
3. Запустит `migrate` (одноразовый, прогонит `alembic upgrade head`).
4. Запустит `redis`, `bot`, `admin`.

Проверка:
```bash
docker compose ps                 # все сервисы Up, migrate — Exit 0
docker compose logs -f bot        # должно быть "Bot is starting in polling mode"
```

Открой Telegram, найди бота по @username, отправь `/start` — должен
ответить. Если нет — `docker compose logs bot` покажет ошибку.

---

## 6. Бэкапы Postgres

Бот без бэкапов — лотерея. Минимум — ежедневный `pg_dump` в директорию
+ ротация. Это уже даёт восстановление при случайном `DROP TABLE`.

```bash
mkdir -p ~/backups
cat > ~/backup.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd /home/deploy/RateYou
DATE=$(date +%Y%m%d-%H%M%S)
docker compose exec -T postgres pg_dump -Fc --no-acl --no-owner \
  -U "${POSTGRES_USER:-rateyou}" "${POSTGRES_DB:-rateyou}" \
  > /home/deploy/backups/rateyou-${DATE}.dump
# Хранить 14 дней
find /home/deploy/backups -name 'rateyou-*.dump' -mtime +14 -delete
EOF
chmod +x ~/backup.sh

# Запустить раз в день в 4 утра
crontab -e
# Добавить:
0 4 * * * /home/deploy/backup.sh >> /home/deploy/backup.log 2>&1
```

**Восстановление:**
```bash
docker compose exec -T postgres pg_restore --clean --no-acl --no-owner \
  -U rateyou -d rateyou < ~/backups/rateyou-YYYYMMDD-HHMMSS.dump
```

> Хранить дампы только на сервере — рискованно (сгорит диск → потеряешь
> бэкапы вместе с базой). Когда вырастешь, добавь выгрузку дампов в
> S3/Backblaze B2/DO Spaces.

---

## 7. Ротация Docker-логов

По умолчанию `docker compose logs` растёт безгранично и однажды забьёт
диск. Добавь глобально:

```bash
sudo tee /etc/docker/daemon.json > /dev/null <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
sudo systemctl restart docker
docker compose up -d                 # пересоздать контейнеры с новыми опциями
```

После этого каждый контейнер хранит максимум 30 МБ логов.

---

## 8. Обновление кода

```bash
cd ~/RateYou
git pull
docker compose up -d --build
```

`migrate` сервис перезапустится, прогонит новые миграции, потом bot/admin
поднимутся на новом образе. `restart: unless-stopped` гарантирует, что
после старта сервера контейнеры поднимутся сами.

> Если хочешь auto-deploy на каждый push в `main` — отдельная задача,
> GitHub Actions + SSH. Скажи, если будем настраивать.

---

## 9. Мониторинг здоровья

Минимум для MVP:

- **Sentry** уже ловит исключения (DSN в `.env`, активен при `ENVIRONMENT=prod`).
- **Логи бота** — `docker compose logs -f bot` от случая к случаю.
- **Команды бота** — отправь `/start` сам себе раз в день. Если хочешь
  автоматизировать — настрой uptime-чекер (UptimeRobot бесплатный) на
  HTTP-эндпоинт админки `http://localhost:8000` через SSH-туннель…
  но это уже overkill для MVP.

---

## Переключение на webhook

Когда захочешь: домен + HTTPS + webhook вместо polling.

1. **Купи домен**, направь A-запись на IP сервера.
2. **Открой 80/443**: `ufw allow http && ufw allow https`.
3. **Caddy** — самый простой reverse-proxy с auto-TLS. Добавь в compose:
   ```yaml
   caddy:
     image: caddy:2-alpine
     restart: unless-stopped
     ports:
       - "80:80"
       - "443:443"
     volumes:
       - ./Caddyfile:/etc/caddy/Caddyfile:ro
       - caddy_data:/data
   volumes:
     caddy_data:
   ```
   `Caddyfile`:
   ```
   bot.example.com {
     reverse_proxy bot:8080
   }
   admin.example.com {
     basicauth {
       admin <bcrypt-hash>
     }
     reverse_proxy admin:8000
   }
   ```
4. **В .env**:
   ```ini
   BOT_USE_WEBHOOK=true
   BOT_WEBHOOK_BASE_URL=https://bot.example.com
   BOT_WEBHOOK_SECRET=<openssl rand -hex 32>
   ```
5. **Открой порт `bot:8080`** в самом compose-сервисе `bot` (для caddy
   внутри сети — без `ports:`).
6. `docker compose up -d --build` — бот сам зарегистрирует webhook у
   Telegram при старте.

После — `docker compose logs caddy` должен показать успешный выпуск
сертификата от Let's Encrypt.

---

## Чек-лист перед открытием бота для пользователей

- [ ] `.env` со сильными паролями, `chmod 600`.
- [ ] `docker-compose.prod.yml` подключён, порты 5432/6379 закрыты.
- [ ] Админка либо за basic-auth+HTTPS, либо на 127.0.0.1.
- [ ] UFW: открыты только 22 (и 80/443 если webhook).
- [ ] Sentry получает события из прод-проекта.
- [ ] Cron-бэкап работает (`tail -f ~/backup.log` через сутки).
- [ ] Docker log rotation настроен.
- [ ] `docker compose ps` — все сервисы `Up`, `migrate` `Exit 0`.
- [ ] `/start` отвечает в Telegram.
