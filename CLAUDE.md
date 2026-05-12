# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Poetry must run under `env -i` on this machine

The user's shell PATH puts `~/.pyenv/versions/3.11.9/bin` ahead of `~/.pyenv/shims`, so a plain `poetry` call picks Python 3.11.9 and fails the project's `requires-python = ">=3.13,<3.14"` check. Wrap every Poetry / `poetry run X` / Alembic / pytest invocation:

```bash
env -i HOME="$HOME" PATH="/Users/vasiliikletkin/.pyenv/versions/3.13.11/bin:/usr/bin:/bin" \
  /Users/vasiliikletkin/.pyenv/versions/3.13.11/bin/poetry <command>
```

Commands below assume this wrapper.

## Commands

```bash
# Tests
poetry run pytest                          # all (~5s)
poetry run pytest tests/unit/              # unit only — no DB/Redis
poetry run pytest tests/integration/       # needs postgres + redis up
poetry run pytest -k <name>                # single test by substring
poetry run pytest tests/unit/domain/identity/test_user.py  # one file

# Lint and type-check
poetry run ruff check src/ tests/
poetry run ruff check --fix src/ tests/
poetry run mypy src/ tests/

# Migrations (operate on the DB pointed to by .env's POSTGRES_*)
poetry run alembic revision --autogenerate -m "describe change"
poetry run alembic upgrade head
poetry run alembic current

# Local infra (Postgres on 5433, Redis on 6380 to avoid host-port conflicts)
docker compose up -d postgres redis        # deps only (dev)
docker compose up -d --build               # everything: bot + admin + migrate

# Entry points (dev)
poetry run python -m src.presentation.bot.main      # bot (polling by default)
poetry run python -m src.presentation.admin.main    # admin on :8000
```

When adding ORM models, also import them in `src/infrastructure/db/models/__init__.py` so Alembic autogenerate sees them in `Base.metadata`.

## i18n workflow

Bot user-facing strings are wrapped with `_(...)` from `aiogram.utils.i18n`. The locale is picked from `from_user.language_code` (via `UserLanguageI18nMiddleware` in `src/presentation/bot/i18n.py`); unsupported codes fall back to `en`.

```bash
# After adding/changing a _("...") string anywhere under src/presentation/bot/:
poetry run pybabel extract -F locales/babel.cfg -o locales/messages.pot src/presentation/bot/
poetry run pybabel update -i locales/messages.pot -d locales

# Translate the new entries in locales/{en,ru}/LC_MESSAGES/messages.po
# Then compile:
poetry run pybabel compile -d locales
```

`Dockerfile` runs `pybabel compile -d locales` during build, so production has `.mo` files even if they're not committed. Locally, you must `pybabel compile` after editing `.po`.

Domain exceptions stay in English (developer/log audience). Bot handlers catch them by type and pick a translated message for the user — they never echo `str(exception)`.

## DDD with 6 bounded contexts

See [docs/context-map.md](docs/context-map.md) for relationships between
contexts (upstream/downstream, partnership, shared kernel, ACL).

Layout under `src/`:

```
domain/{identity,profile,rating,discovery,subscription,payment,shared}/
application/<same contexts>/
infrastructure/db/{models,mappers,repositories}/  +  payment/  +  discovery/
presentation/{bot,admin,di}/
```

**Domain has zero framework imports.** No `sqlalchemy`, no `aiogram`, no `dishka`. If you find yourself reaching for one in `src/domain/`, you're in the wrong layer.

**ORM models ≠ Entities.** Every context with persistence has three files:
- `infrastructure/db/models/<ctx>.py` — SQLAlchemy `Mapped[...]` columns
- `infrastructure/db/mappers/<ctx>.py` — `entity_to_orm` / `orm_to_entity`
- `infrastructure/db/repositories/<ctx>.py` — implements the domain `Protocol`

The domain `Protocol` (e.g. `IUserRepository`) lives in `domain/<ctx>/repositories.py`. Use cases take the Protocol; dishka injects the concrete `Repository`.

**One UoW per request.** Each Telegram update / HTTP request gets a fresh `AsyncSession` (REQUEST scope in dishka). All repos in a use case share that session. `SqlAlchemyUnitOfWork.commit()` commits everything atomically; an unhandled exception leaves nothing committed.

**Cross-context read in Discovery.** `DiscoveryRepository.find_next_candidate_for(viewer_id, min_rating, exclude_owner_ids)` JOINs `profiles` + `ratings` + `profile_score_summaries`. The use case `GetNextProfileForRatingUseCase` orchestrates: reads premium tier from `ISubscriptionRepository`, reads skipped IDs from `ISkipRegistry` (Redis), passes both to the repo. This is the only legitimate cross-context query.

## Code conventions

- **`now: datetime` is injected** into every entity method that touches time (`User.ban(reason, now)`, `Subscription.activate(..., now)`). Entities never read the clock themselves — keeps them deterministic and testable.
- **Aggregate factories named for domain intent**: `User.register()`, `Profile.create()`, `Rating.give()`, `Subscription.activate()`, `Transaction.create_invoice()`. Don't use raw `__init__` from outside the aggregate.
- **Entities are mutable dataclasses**; VOs are `@dataclass(frozen=True, slots=True)`. VOs validate in `__post_init__` and raise their own domain exceptions; normalization (trimming whitespace, etc.) uses `object.__setattr__` after validation.
- **Exception names omit the `Error` suffix** by deliberate convention — they read as domain concepts (`UserIsBanned`, `CannotRateSelf`, `ProfileAlreadyExists`, `InvalidStatusTransition`). Ruff `N818` is disabled project-wide for this.
- **Idempotency at the use case** for natural retries: `RegisterUserUseCase` returns existing user if telegram_id was seen, `RateUserUseCase` updates score on re-rating (UNIQUE on `(rater_id, rated_id)`), `ConfirmPaymentUseCase` swallows `InvalidStatusTransition` when Telegram retries `successful_payment`.
- **`ProfileScoreSummary` is a read model**, not an aggregate. `RateUserUseCase` mutates the `Rating` AND recomputes+upserts the summary in the same transaction.

## Bot specifics

- **Handlers take `FromDishka[X]` directly in their signatures**; `setup_dishka(..., auto_inject=True)` does the wiring. No `@inject` decorator needed.
- **FSM state lives in Redis** (`aiogram.fsm.storage.redis.RedisStorage`). Each FSM stores the relevant aggregate id (e.g. `user_id`, `profile_id`) on the first step so later handlers don't re-query.
- **Middlewares**: `ThrottlingMiddleware` (cheap Redis `SET NX EX`) runs before `BanCheckMiddleware` (DB lookup via `dishka_container` from `data`). Both registered on `dp.message` and `dp.callback_query`.
- **Callback data is capped at 64 bytes**. Rate buttons use `rate:<uuid>:<score>` (44 bytes max).
- **Polling vs webhook**: `BOT_USE_WEBHOOK=true` → aiohttp on `:8080/webhook`. Default is polling.
- **Telegram Stars**: `bot.send_invoice(currency="XTR", provider_token="")`. Payload is `str(transaction.id.value)`; comes back in `successful_payment.invoice_payload`. `Transaction.payer_telegram_id` is **denormalized** so `bot.refund_star_payment` doesn't need a User repo lookup.

## Admin specifics

- **Starlette-Admin `ModelView` uses string field names**, not `UserORM.id` references. The stubs are stricter than the runtime; per-module overrides in `pyproject.toml` (`tool.mypy.overrides` and `tool.ruff.lint.per-file-ignores`) cover `src/presentation/admin/views.py`.
- **`can_create = False` / `can_edit = False`** have `# type: ignore[assignment]` because Starlette-Admin's base class types them as `Callable`. Banning a user happens via Edit (toggle `is_banned`, fill `ban_reason`); no row action yet.
- Admin runs as its own process via direct `AsyncEngine`. **dishka is not wired into admin** — adding custom actions that need use cases (e.g. Refund) requires that wiring.

## Testing conventions

- **Engine is function-scoped** in `tests/integration/conftest.py` because asyncpg + pytest-asyncio's per-test event loop clash with a session-scoped engine. After each test, all tables get `TRUNCATE ... CASCADE` rather than savepoint-rollback (which also fights asyncpg).
- **Redis tests** use the `redis_client` fixture that deletes `skipped:*` and `throttle:*` keys after each test to avoid polluting the FSM keyspace.
- **Use case unit tests use Fake repos as dataclasses** (`FakeUserRepository`, `FakeUoW`, etc.) — structural typing means they don't need to inherit any Protocol. Look at `tests/unit/application/*/test_*.py` for the pattern.
- **DI smoke tests** in `tests/integration/composition/test_container.py` resolve key use cases through the real dishka container; they catch broken provider registrations that mypy alone misses.

## Currently deferred (won't find in code)

- **Multi-photo profile.** `Profile.photo` is a single `PhotoFileId`. Multi-photo would make `Photo` an entity inside the `Profile` aggregate with its own table and reconcile logic.
- **Outbox / event bus.** Cross-aggregate effects happen synchronously in the same use case + transaction. There is no async event delivery.
- **Refund row action in admin.** `RefundPaymentUseCase` exists and works; admin can't trigger it because dishka isn't wired into admin. Use the use case directly via a CLI / script.
- **Skip per-key TTL.** `RedisSkipRegistry` puts TTL on the whole SET — late skips extend the lifetime of earlier ones in the same set. Acceptable for MVP.

## Memory

`~/.claude/projects/-Users-vasiliikletkin-SynologyDrive-Development-MyProjects-RateYou/memory/` holds the user's preferences (e.g. always-latest dependencies) and the documented Poetry workaround. CLAUDE.md repeats the workaround because the memory is per-machine; CLAUDE.md is checked in.
