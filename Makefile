#!make
include .env

# Все Python-команды — внутри dev-контейнера. postgres/redis поднимаются
# через depends_on автоматически. См. сервис `dev` в docker-compose.yml
# и stage `dev` в Dockerfile. Для команд без БД/Redis — DEV_NODEPS.
DEV        = docker compose run --rm dev
DEV_NODEPS = docker compose run --rm --no-deps dev

# ─── Docker ───────────────────────────────────────────────────────────────────

## Поднять только зависимости (postgres + redis)
up-deps:
	docker compose up -d postgres redis

## Поднять всё: postgres, redis, migrate, bot, admin
up:
	docker compose up -d --build

## Собрать все образы, включая dev
build:
	docker compose --profile dev build

## Остановить все контейнеры
down:
	docker compose down

## Остановить и удалить volumes (полный сброс БД и Redis)
down-volumes:
	docker compose down -v

## Логи всех сервисов
logs:
	docker compose logs -f --tail=200

## Логи бота
logs-bot:
	docker compose logs -f --tail=200 bot

## Логи админки
logs-admin:
	docker compose logs -f --tail=200 admin

# ─── Entry points (foreground) ────────────────────────────────────────────────

## Бот в foreground (Ctrl+C — стоп)
bot:
	docker compose up bot

## Админка в foreground
admin:
	docker compose up admin

## Bash внутри dev-контейнера (для ручных команд)
shell:
	$(DEV) bash

# ─── Alembic / миграции ───────────────────────────────────────────────────────

## Создать миграцию: make migration M="describe change"
migration:
	@test -n "$(M)" || (echo "Использование: make migration M=\"описание\"" && exit 1)
	$(DEV) alembic revision --autogenerate -m "$(M)"

## Применить все миграции
migrate:
	$(DEV) alembic upgrade head

## Откатить последнюю миграцию
migrate-down:
	$(DEV) alembic downgrade -1

## Текущая ревизия
migrate-current:
	$(DEV) alembic current

## История миграций
migrate-history:
	$(DEV_NODEPS) alembic history

# ─── PostgreSQL ───────────────────────────────────────────────────────────────

## Создать БД
dcreatedb:
	docker compose exec postgres createdb -U ${POSTGRES_USER} ${POSTGRES_DB}

## Удалить БД
ddeletedb:
	docker compose exec postgres dropdb -U ${POSTGRES_USER} ${POSTGRES_DB}

## Создать дамп
dcreatedump:
	docker compose exec postgres pg_dump -Fc --no-acl --no-owner -U ${POSTGRES_USER} ${POSTGRES_DB} > ./${POSTGRES_DB}.dump

## Загрузить дамп
dloaddump:
	docker compose exec -T postgres pg_restore --verbose --clean --no-acl --no-owner -U ${POSTGRES_USER} -d ${POSTGRES_DB} < ${POSTGRES_DB}.dump

## psql внутри контейнера postgres
psql:
	docker compose exec postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB}

# ─── Мониторинг БД ────────────────────────────────────────────────────────────

## Соединения по application_name
dbconns:
	docker compose exec postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "SELECT application_name, state, count(*) FROM pg_stat_activity GROUP BY application_name, state ORDER BY count DESC;"

## Детали всех соединений: PID, время создания, idle duration
dbconns-detail:
	docker compose exec postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "SELECT pid, application_name, state, backend_start, state_change, now() - state_change AS idle_duration FROM pg_stat_activity WHERE datname = current_database() ORDER BY application_name, state_change;"

## Idle-соединения с текстом последнего запроса
dbconns-queries:
	docker compose exec postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "SELECT application_name, left(query, 200) AS query, state, now() - state_change AS idle_duration FROM pg_stat_activity WHERE datname = current_database() AND state = 'idle' ORDER BY idle_duration DESC;"

## Воронка привлечения по источникам за N дней (по умолчанию 30):
## make funnel [D=7]. Источник — payload диплинка /start: метка кампании
## (?start=habr) или пригласивший человек (?start=<telegram_id>); справочник
## в acquisition_sources, связка user->источник в acquisitions, пишется один
## раз при регистрации. Люди-источники схлопнуты в строку (referral), чтобы
## не раздувать отчёт; пусто = органика.
## Все join'ы строго 1:1 (acquisitions/search_preferences — PK по user_id,
## profiles.owner_id — UNIQUE, source — PK справочника), поэтому count(*)
## не задваивает. Оценки — через EXISTS: join к ratings размножил бы строки.
D ?= 30
funnel:
	docker compose exec postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "\
	SELECT coalesce(CASE WHEN s.referrer_id IS NOT NULL \
	                     THEN '(referral)' ELSE s.code END, \
	                '(organic)') AS source, \
	       count(*) AS started, \
	       count(*) FILTER (WHERE sp.location IS NOT NULL) AS onboarded, \
	       count(*) FILTER (WHERE EXISTS ( \
	           SELECT 1 FROM ratings r WHERE r.rater_id = u.id)) AS rated, \
	       count(p.id) AS profiles \
	FROM users u \
	LEFT JOIN acquisitions a ON a.user_id = u.id \
	LEFT JOIN acquisition_sources s ON s.id = a.source_id \
	LEFT JOIN search_preferences sp ON sp.user_id = u.id \
	LEFT JOIN profiles p ON p.owner_id = u.id \
	WHERE u.created_at > now() - interval '$(D) days' \
	GROUP BY 1 ORDER BY started DESC;"

## Размеры таблиц
dbsizes:
	docker compose exec postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "SELECT relname AS table, pg_size_pretty(pg_total_relation_size(relid)) AS total_size FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC;"

# ─── Redis ────────────────────────────────────────────────────────────────────

## redis-cli внутри контейнера
redis-cli:
	docker compose exec redis redis-cli

## Все FSM-ключи aiogram
redis-fsm-keys:
	docker compose exec redis redis-cli --scan --pattern 'fsm:*'

## Throttling-ключи
redis-throttle-keys:
	docker compose exec redis redis-cli --scan --pattern 'throttle:*'

## Skip-ключи (RedisSkipRegistry в Discovery): ключ skipped:<UserId>
## хранит SET внутренних UserId анкет, пропущенных этим зрителем
redis-skip-keys:
	docker compose exec redis redis-cli --scan --pattern 'skipped:*'

## Сбросить весь Redis (FSM + throttle + skip)
redis-flush:
	docker compose exec redis redis-cli FLUSHDB
	@echo "Redis очищен"

# ─── i18n (pybabel) ───────────────────────────────────────────────────────────

## Извлечь строки из src/presentation/bot/ → messages.pot + обновить .po
i18n-extract:
	$(DEV_NODEPS) pybabel extract -F locales/babel.cfg -o locales/messages.pot src/presentation/bot/
	$(DEV_NODEPS) pybabel update -i locales/messages.pot -d locales

## Скомпилировать .po → .mo
i18n-compile:
	$(DEV_NODEPS) pybabel compile -d locales

## Полный цикл: extract + update + compile
i18n:
	make i18n-extract && make i18n-compile

# ─── Тесты ────────────────────────────────────────────────────────────────────

## Все тесты
test:
	$(DEV) pytest

## Только unit (без БД/Redis)
test-unit:
	$(DEV_NODEPS) pytest tests/unit/

## Интеграционные (нужны postgres + redis)
test-integration:
	$(DEV) pytest tests/integration/

## По подстроке: make test-k K=test_register
test-k:
	@test -n "$(K)" || (echo "Использование: make test-k K=test_name" && exit 1)
	$(DEV) pytest -k $(K)

# ─── Линт и тайпчек ───────────────────────────────────────────────────────────

## Ruff: проверка
lint:
	$(DEV_NODEPS) ruff check src/ tests/

## Ruff: автофикс
lint-fix:
	$(DEV_NODEPS) ruff check --fix src/ tests/

## mypy
typecheck:
	$(DEV_NODEPS) mypy src/ tests/

## Линт + типы + тесты — то, что гоняет CI
check:
	make lint && make typecheck && make test

# ─── Seeds ────────────────────────────────────────────────────────────────────

## Заполнить БД тестовыми профилями
seed:
	$(DEV) python -m scripts.seed_profiles
