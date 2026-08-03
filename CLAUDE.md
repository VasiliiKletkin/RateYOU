# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Production is live — push to main deploys

The bot runs on a Hetzner VPS. `.github/workflows/cd.yml` on every push to `main`: checks → image build to GHCR (`ghcr.io/vasiliikletkin/rateyou:latest`) → SSH deploy via [docker-compose.prod.yml](docker-compose.prod.yml), where the `migrate` service applies Alembic migrations **automatically against real data**. Treat migrations as production changes, not dev conveniences. `.github/workflows/ci.yml` runs ruff + mypy + pytest on PRs; both reuse `checks.yml`. Server setup is documented in [docs/deployment.md](docs/deployment.md).

## Poetry must run under `env -i` on this machine

The user's shell PATH puts `~/.pyenv/versions/3.11.9/bin` ahead of `~/.pyenv/shims`, so a plain `poetry` call picks Python 3.11.9 and fails the project's `requires-python = ">=3.13,<3.14"` check. Wrap every host-side Poetry / `poetry run X` / Alembic / pytest invocation:

```bash
env -i HOME="$HOME" PATH="/Users/vasiliikletkin/.pyenv/versions/3.13.11/bin:/usr/bin:/bin" \
  /Users/vasiliikletkin/.pyenv/versions/3.13.11/bin/poetry <command>
```

The `Makefile` sidesteps this entirely by running everything inside the `dev` container — prefer it when Docker is up.

## Commands

The Makefile is the intended interface. Every Python command runs in the one-shot `dev` service (`docker compose run --rm dev …`, `profiles: [dev]` keeps it out of `docker compose up`); `postgres`/`redis` come up via `depends_on`. Targets that need no DB add `--no-deps`.

```bash
make check              # lint + typecheck + test — what CI runs
make test               # all tests
make test-unit          # unit only, no DB/Redis
make test-integration   # needs postgres + redis
make test-k K=register  # single test by substring
make lint / lint-fix / typecheck
make up-deps            # postgres + redis only
make up                 # full stack: migrate, bot, admin, worker, scheduler
make migration M="describe change"   # alembic revision --autogenerate
make migrate / migrate-down / migrate-current
make shell              # bash inside the dev container
make seed               # scripts/seed_profiles.py
```

There are also DB/Redis inspection targets (`psql`, `dbconns`, `dbsizes`, `redis-fsm-keys`, `redis-skip-keys`, `redis-flush`) — read the Makefile before hand-rolling a `docker compose exec`.

Host-side equivalents (need the `env -i` wrapper above, plus `make up-deps` for anything touching the DB):

```bash
poetry run pytest tests/unit/domain/identity/test_user.py
poetry run ruff check src/ tests/
poetry run mypy src/ tests/
poetry run python -m src.presentation.bot.main     # bot, polling by default
poetry run python -m src.presentation.admin.main   # admin on :8000
poetry run taskiq worker    src.presentation.tasks.broker:broker    src.presentation.tasks.broadcast
poetry run taskiq scheduler src.presentation.tasks.broker:scheduler src.presentation.tasks.broadcast
```

The taskiq task module must be passed explicitly — that's what registers tasks and their `schedule=[…]` labels. Keep `scheduler` at one replica; two would double every broadcast.

Integration tests run against `rateyou_test`, never the dev `rateyou` DB: `pytest-env` forces `POSTGRES_DB=rateyou_test` in `pyproject.toml`'s `[tool.pytest.ini_options].env` before pydantic-settings reads `.env`, and the session fixture in `tests/integration/conftest.py` refuses to bootstrap a DB whose name lacks `test`. That fixture creates the DB and runs `alembic upgrade head` automatically, so after a schema change you just run pytest. The dev DB still needs `make migrate` manually.

When adding ORM models, import them in `src/infrastructure/db/models/__init__.py` so Alembic autogenerate sees them in `Base.metadata`.

## i18n workflow

22 locales (`locales/{en,ru,es,pt,de,fr,it,tr,uk,pl,ar,fa,id,vi,zh,hi,bn,am,uz,ko,ja,th}`). User-facing strings are wrapped with `_(…)` from `aiogram.utils.i18n`.

**Extract from `src/presentation/`, not `src/presentation/bot/`.** Taskiq broadcasts in `src/presentation/tasks/broadcast.py` contain `_(…)` strings; scanning only `bot/` silently drops them from the catalog. `make i18n-extract` currently scans `bot/` only and has this bug — until it's fixed, run extraction by hand:

```bash
poetry run pybabel extract -F locales/babel.cfg -o locales/messages.pot src/presentation/
poetry run pybabel update -i locales/messages.pot -d locales
# translate new entries in locales/*/LC_MESSAGES/messages.po, then:
make i18n-compile
```

`Dockerfile` runs `pybabel compile -d locales` in both stages, so containers always have `.mo` files. Locally you must compile after editing `.po`.

**Locale selection is DB-first.** `UserLanguageI18nMiddleware` (`src/presentation/bot/i18n.py`) reads `User.language` via the request-scope dishka container; `from_user.language_code` is only the fallback for users not yet in the DB, and only on their first `/start`. After that the stored value wins and changes only via `/settings`. `Language` is a `StrEnum` of ISO 639-1 codes; `normalize_language` strips the region suffix (`ru-RU` → `ru`) and falls back to `en`.

Domain exceptions stay in English (developer/log audience). Bot handlers catch them by type and pick a translated message — they never echo `str(exception)`.

## DDD with 7 bounded contexts

`identity`, `profile`, `rating`, `discovery`, `subscription`, `payment`, `referral`. See [docs/context-map.md](docs/context-map.md) — note it predates the Referral context and still says "six".

```
domain/<ctx>/         entities, value_objects, repositories (Protocol), services, events, exceptions
application/<ctx>/    use cases, DTOs, event handlers
infrastructure/       db/{models,repositories}, payment/, discovery/, geocoding/, events/, observability/
presentation/         bot/, admin/, tasks/, di/
```

**Domain has zero framework imports.** No `sqlalchemy`, no `aiogram`, no `dishka` under `src/domain/`.

**ORM models ≠ entities, and there is no mapper layer.** Each repository in `infrastructure/db/repositories/` constructs the entity (or the ORM row) inline. The cost is deliberate: `Profile` is built in three places, `Subscription`/`Rating`/`User` in two or three each, so adding an entity field means visiting every construction site. The only shared translation helper is `infrastructure/db/geo.py` (`location_to_wkt` / `wkb_to_location`), which is PostGIS geometry plumbing rather than entity mapping.

The domain `Protocol` (e.g. `IUserRepository`) lives in `domain/<ctx>/repositories.py`. Use cases take the Protocol; dishka injects the concrete class.

**One UoW per request.** Each Telegram update / HTTP request / taskiq run gets a fresh `AsyncSession` (REQUEST scope in dishka). All repos in a use case share it; `SqlAlchemyUnitOfWork.commit()` commits atomically.

**Domain events, dispatched in-process.** Aggregates record events as state mutates (`Transaction._events`, `Rating._events`) and the use case publishes them with `event_bus.publish_all(agg.pull_events())` *before* `uow.commit()`. `InMemoryEventBus` is REQUEST-scoped, so handlers hold repositories on the same session and their writes join the same transaction — a failing handler rolls the whole operation back. Wiring lives in `presentation/di/events.py`:

| Event | Handler | Effect |
|---|---|---|
| `RatingGiven` / `RatingWithdrawn` | `OnRatingGiven` / `OnRatingWithdrawn` | recompute `ProfileScoreSummary` |
| `PaymentConfirmed` | `OnPaymentConfirmed` | activate tier from `purpose` (`"premium:<tier>"`) |
| `PaymentRefunded` | `OnPaymentRefunded` | revoke the grant linked to that transaction |

**Specifications compile to SQL at the infrastructure boundary.** `GetNextProfileForRatingUseCase` composes `Specification`s (visible, not own, not already rated, gender preference, min-rating for premium, skipped-owner cooldown) with `&`; `DiscoverySpecApplier` translates the tree into WHERE/JOIN clauses. Domain code stays SQL-free. Adding a spec means adding a branch to the applier — it raises on unknown specs. `DiscoveryRepository.find_next` orders by PostGIS `ST_Distance` (distance ASC, NULLS LAST); it must `selectinload(ProfileORM.photos)` explicitly because `lazy="selectin"` is unreliable when the outer SELECT mixes the entity with extra columns.

**The feed's origin is `SearchPreferences.location`, not the viewer's profile.** A user can browse without ever creating a profile: the nullable Geography column on `search_preferences` is the point the feed sorts around. When it's unset, `GetNextProfileForRatingUseCase` raises `SearchLocationNotSet` — deliberately distinct from returning `None` ("no candidates left"); handlers turn the exception into the city-picker prompt. `/create` seeds the search origin from the new profile's location so the feed works immediately after onboarding, and migration `f7d2a4c9b6e1` backfilled existing rows from `profiles.location`.

**Domain services own cross-aggregate logic but never commit** — `RatingFulfillmentService`, `SubscriptionActivationService`, `ReferralRewardService`. The use case above them owns the transaction boundary.

## Code conventions

- **`now: datetime` is injected** into every entity/service method that touches time (`User.ban(reason, now)`, `Subscription.create_bonus(..., now)`). Entities never read the clock.
- **Aggregate factories named for domain intent**: `User.register()`, `Profile.create()`, `Rating.give()`, `Subscription.create_purchase()` / `create_bonus()`, `Transaction.create_invoice()`, `Referral.create_pending()`.
- **Entities are mutable dataclasses**; VOs are `@dataclass(frozen=True, slots=True)`. VOs validate in `__post_init__` and raise their own domain exceptions; normalization uses `object.__setattr__` after validation.
- **Exception names omit the `Error` suffix** by deliberate convention (`UserIsBanned`, `CannotRateSelf`, `SelfReferral`, `InvalidStatusTransition`). Ruff `N818` is disabled project-wide for this.
- **Idempotency at the use case**: `RegisterUserUseCase` returns the existing user for a known telegram_id (and that early return is what stops the welcome bonus being granted twice), `RateUserUseCase` updates the score on re-rating (UNIQUE on `(rater_id, rated_id)`), `Referral.mark_rewarded` won't overwrite an existing timestamp. Telegram's `successful_payment` retries are absorbed one level higher: `ConfirmPaymentUseCase` lets `InvalidStatusTransition` propagate and the bot handler in `handlers/premium.py` swallows it.
- **`ProfileScoreSummary` is a read model**, not an aggregate — recomputed by the `RatingGiven`/`RatingWithdrawn` handlers, never mutated directly by a use case.
- **Static catalogs live in code, not the DB**: `TIER_CATALOG` (prices in Stars, durations), `PER_REFERRAL_REWARD_DAYS` / `MILESTONE_INTERVAL`, `WELCOME_BONUS_DAYS = 30`. Changing a price is a code change plus a release.
- Repositories raise a bare `ValueError(f"<Entity> <id> not found for update")` on a missing row — a known wart, repeated across the repository files.

## Bot specifics

- **Handlers take `FromDishka[X]` directly in their signatures**; `setup_dishka(..., auto_inject=True)` wires it. No `@inject` decorator on bot handlers (taskiq tasks *do* need `@inject`).
- **FSM state lives in Redis** (`RedisStorage`), with TTLs from `RedisConfig` (`fsm_state_ttl_seconds`, 24h). Each FSM stores the relevant aggregate id on the first step so later handlers don't re-query.
- **`search_location.py` owns the standalone city picker** (`SetSearchLocation` FSM, `/setcity`), reused by `/start` and `/feed` when no search area is set. Its router is registered **last** in `handlers/__init__.py` — it has an in-state catch-all that must not shadow other routers' commands — and its text handler filters out `/`-prefixed messages so a command typed mid-flow isn't geocoded as a city name. `feed.py` keeps its own local copy of the prompt (`_prompt_search_city`) because `search_location` imports `show_next_or_done` from `feed` — importing back would create a cycle.
- **Media-group photo buffering is in-process.** `create_profile.py` and `edit_profile.py` each keep their own module-level `dict` plus a ~1.2s debounce to collect a Telegram album into one `Photos` VO. Duplicated between the two handlers, and it does not survive a restart or a second bot replica — unlike the FSM itself.
- **Middlewares**: `ThrottlingMiddleware` (cheap Redis `SET NX EX`) runs before `BanCheckMiddleware` (DB lookup via `dishka_container` from `data`). Both on `dp.message` and `dp.callback_query`.
- **Callback data is capped at 64 bytes.** Prefixed forms: `rate:<uuid>:<score>` (the widest, 44 bytes), `skip:<uuid>`, `edit_field:<name>`, `buy:<tier>`, `gender:<v>`, `genderpref:<v>`, `geopick:<idx>`, and `/settings`' own `setpref:` / `setrating:` / `setlang:`. `geopick:` buttons carry only an index — the geocoder candidates are parked in FSM data (both in `/create` and the city picker). Bare actions (`openpref`, `openrating`, `openlang`, `togglenotify`, `show_my_ratings`) are module constants in `handlers/settings.py`, not literals at the call site.
- **Polling vs webhook**: `BOT_USE_WEBHOOK=true` → aiohttp on `:8080/webhook` (requires `BOT_WEBHOOK_BASE_URL`); default is polling.
- **Telegram Stars**: `bot.send_invoice(currency="XTR", provider_token="")`. Payload is `str(transaction.id.value)` and comes back in `successful_payment.invoice_payload`. The Payment domain carries no Telegram fields — `RefundPaymentUseCase` resolves `payer_id → User.telegram_id` through `IUserRepository`, and `TelegramStarsGateway` is the ACL for `"XTR"` and `telegram_payment_charge_id`.
- **Geocoding**: free-text city input goes through `CachedGeocoder` → `NominatimGeocoder`. Public Nominatim allows ~1 req/s and requires the identifying `User-Agent` in `GeocodingConfig`; hits cache for 30 days, misses for an hour, failures are never cached.

## Background tasks

`src/presentation/tasks/` runs under taskiq with the same dishka providers as the bot, so tasks reuse the very same use cases with a fresh REQUEST scope per run. `broadcast_new_profiles` (daily, `cron: 0 18 * * *`) asks `NotifyAboutNewProfilesUseCase` for an audience — everyone with a visible profile, minus banned users, minus those with `notifications_enabled=False`, minus anyone for whom every new profile is their own — then sends at 25 msg/s, honouring `TelegramRetryAfter` once and treating `TelegramForbiddenError` as an expected loss. The run watermark is a plain Redis key (`broadcast:new_profiles:last_run_at`), stamped *before* the query so profiles created mid-run land in the next window; with no watermark it looks back 24h. None of this is currently covered by tests.

## Admin specifics

- **Starlette-Admin `ModelView` uses string field names**, not `UserORM.id` references. The stubs are stricter than the runtime; per-module overrides in `pyproject.toml` (`tool.mypy.overrides`, `tool.ruff.lint.per-file-ignores`) cover `src/presentation/admin/views.py`.
- **`can_create = False` / `can_edit = False`** carry `# type: ignore[assignment]` because the base class types them as `Callable`. Banning happens via Edit (toggle `is_banned`, fill `ban_reason`); there is no row action.
- Admin is its own process with its own `AsyncEngine`. **dishka is not wired into admin**, so it cannot call use cases.

## Testing conventions

- **Engine is function-scoped** in `tests/integration/conftest.py` — asyncpg plus pytest-asyncio's per-test loop clash with a session-scoped engine. Cleanup is `TRUNCATE … CASCADE` after each test rather than savepoint-rollback (which also fights asyncpg).
- **Redis tests** use the `redis_client` fixture, which deletes `skipped:*` and `throttle:*` after each test to avoid polluting the FSM keyspace.
- **Use case tests use Fake repos as dataclasses** — structural typing means they don't inherit any Protocol. Two conflicting styles currently coexist: most files declare `class Fake…` inline, while `tests/_fakes/referral.py` is a shared module. Follow whichever the file you're editing already uses, and prefer consolidating over adding a third copy.
- **DI smoke tests** in `tests/integration/composition/test_container.py` resolve key use cases through the real dishka container; they catch broken provider registrations mypy alone misses.

## Known gaps (won't find in code)

- **No outbox.** The event bus is in-process and synchronous; cross-process delivery would need an outbox table + worker.
- **Refund row action in admin.** `RefundPaymentUseCase` works, but admin can't reach it without dishka wiring. Drive it from a script.
- **Skip cooldown TTL is per-set, not per-key.** `RedisSkipRegistry` re-expires the whole SET on every skip, so a stream of skips keeps earlier entries alive. Acceptable for MVP.
- **`NotifyAboutNewProfilesUseCase` loads the whole audience into memory** and does an O(n·m) membership scan. Fine at current scale, not beyond it.

## Memory

`~/.claude/projects/-Users-vasiliikletkin-SynologyDrive-Development-MyProjects-RateYou/memory/` holds the user's preferences and per-machine notes. CLAUDE.md repeats the Poetry workaround because the memory is per-machine while CLAUDE.md is checked in.
