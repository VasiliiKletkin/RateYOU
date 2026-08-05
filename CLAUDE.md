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

## User-facing flows (the business logic)

Cross-cutting rules first:

- **Every handler starts with the idempotent `RegisterUserUseCase`**, so any command works as the user's first-ever message — /start is not a prerequisite (a user's first-ever interaction can be /refer or a `rate:` button tap).
- `ThrottlingMiddleware` then `BanCheckMiddleware` run before every handler; banned users are silently blocked.
- The product loop: browse & rate needs only the browse onboarding (gender preference + **search location**); having your **own profile** is what makes you ratable — and past `FREE_RATINGS_WITHOUT_PROFILE = 15` ratings, what lets you keep rating (the reciprocity gate). Premium gates exactly two things: the min-rating feed filter and /my_ratings.

### `/start [<referrer_telegram_id>]`

Registration + routing. On the new-user branch (and only there), three writes land in **one transaction**: the `users` row, a `WELCOME_BONUS_DAYS = 30` premium BONUS grant (the idempotent early-return for existing users is the double-grant guard), and — when the deep-link payload resolves to a known, non-self user — a *pending* `Referral` (`rewarded_at=NULL`). Malformed/unknown/self payloads are silently dropped; registration always succeeds. /start is also where the cached `@username` is (re)captured — on every call, not just the first. Then: search location set → "welcome back" naming /feed and /create; not set → welcome text + browse onboarding (`SetSearchLocation` FSM): "who would you like to rate?" (`genderpref:` buttons → `SearchPreferences.gender_preference`), then the city picker.

### `/feed` → `rate:` / `skip:` loop

The core loop; needs a search location but **not** an own profile (`show_next_or_done` catches `SearchLocationNotSet` and starts the browse onboarding instead). Profile-less browsing is capped: after `FREE_RATINGS_WITHOUT_PROFILE = 15` ratings the use case raises `ProfileRequiredToContinue` and the handler answers with a "/create to keep rating" prompt — the reciprocity gate that converts lurkers. Re-rating doesn't burn quota (the count is per-person), and the gate vanishes the moment a profile exists.

Candidate selection (`GetNextProfileForRatingUseCase`): visible profiles, not the viewer's own, not already rated by them, matching the viewer's gender preference, above their min-rating threshold (only if premium **and** threshold > 0), excluding owners in the viewer's Redis skip set — ordered by `ST_Distance` from the viewer's search location, nearest first, NULLS LAST (profiles without location come last, not never).

Card rendering: caption is `<b>name, age</b>` + distance (`350 m` / `5.4 km`) + bio if present. One photo → `answer_photo` with the rating keyboard attached; 2–10 photos → `answer_media_group` + a separate "Rate this profile:" message carrying the keyboard (Telegram media groups can't have inline keyboards). Buttons: `rate:<owner_uuid>:<1-10>` and `skip:<owner_uuid>`.

- **rate** → `RateUserUseCase`: `RatingFulfillmentService` gives or updates the rating (re-rating the same person replaces the score — UNIQUE on `(rater_id, rated_id)`), `RatingGiven` recomputes `ProfileScoreSummary` in the same UoW. `CannotRateSelf` → alert; then, in order: "Rated X/10 ✓" toast → the rated user gets a "⭐ Someone just rated you: X/10" DM **in their stored locale** (skipped if banned or gone; `TelegramAPIError` suppressed — a blocked bot must not break the rater's flow) → old keyboard stripped → rater sees "📊 Their average: N/10 (from M ratings)" → next card. The rater's identity is *not* revealed in the DM — that's what /my_ratings sells.
- **skip** → `SkipProfileUseCase` → Redis SET `skipped:<viewer_id>` (no DB write, no UoW), TTL `skip_ttl_seconds = 3600`; the TTL is per-set, so every skip refreshes the whole set's hour. Keyboard stripped → next card.
- No candidates left → "No more profiles to rate. Come back later!".

### `/create` — profile FSM (`CreateProfile` states)

Guard: existing profile → "You already have a profile", no FSM entered. Steps, each with a retry-on-invalid message:

1. **name** — `Name` VO, 1–50 non-empty chars.
2. **age** — `Age` VO, int 18–100.
3. **gender** — `gender:male|female` buttons (no "other" by product decision).
4. **gender preference** — "who would you like to rate": `genderpref:male|female|any`.
5. **location** — share-location reply button, or typed city → Nominatim geocode in the user's locale → up to N candidates parked in FSM data → `geopick:<idx>` buttons (index only; the 64-byte callback cap forbids embedding coordinates). Commands are filtered out (`~F.text.startswith("/")`) so /feed typed mid-flow isn't geocoded. Geocoder down → "share location instead"; typed-city is the only path for Telegram Desktop, which can't send locations.
6. **bio** — `Bio` VO ≤ 500 chars, or /skip for empty.
7. **photos** — up to `Photos.MAX_COUNT`, collected via the in-process media-group buffer (~1.2 s debounce; first handler in becomes the leader and flushes).

Finalize re-resolves the user via `RegisterUserUseCase` (never trusts the FSM-stored UUID — the row may have been wiped mid-flow), then: `CreateProfileUseCase` (which also triggers **referral payout**, see /refer) → gender preference persisted into `SearchPreferences` → search location seeded from the profile's location → FSM cleared → confirmation → **straight into the feed** (no "now send /feed" dead end). `ProfileAlreadyExists` → bail politely.

### `/edit` — field-at-a-time profile editing (`EditProfile` states)

Requires a profile ("No profile to edit. Use /create first."). Inline menu `edit_field:<name|age|gender|bio|photo|location|done>`; each field edit validates with the same VOs as /create, applies **immediately** via `EditProfileUseCase` (no draft state), and returns to the menu. Location supports the same share-or-typed-city path, with its own copy of the geocode-candidates dance; photos use a separate module-level buffer from /create's. Bio: /skip *clears* it. Done → "Saved. /feed to keep rating."

### `/setcity` — browse onboarding & search-origin picker (`SetSearchLocation` FSM)

What unblocks browsing without a profile. Two states: `waiting_for_gender_preference` ("who would you like to rate?", entered from /start and /feed on first onboarding) → `waiting_for_location` (same share-or-type-city UX as /create's location step, writes to `SearchPreferences.location` via `UpdateSearchLocationUseCase`, which creates the prefs row if missing). The explicit /setcity command re-enters at the location step directly — existing users change city without being re-asked the gender question. On save: "✅ Search area saved" → **straight into the feed**. Its router is registered last and excludes `/`-prefixed text so commands typed mid-picker fall through to their own handlers; `feed.py` keeps a local copy of the onboarding entry (`_start_browse_onboarding`) to avoid an import cycle.

### `/cancel`

Global FSM abort — registered with `StateFilter("*")` in `create_profile.py` but clears *any* flow's state; outside a flow answers "Nothing to cancel."

### `/settings`

One inline card ("Settings"), always edited in place (`edit_text`; the "message is not modified" Telegram error is suppressed when a picker re-selects the current value). Four rows, each showing its current value:

- **Show me** (`openpref` → `setpref:<male|female|any>`) — gender preference, same aggregate /create seeds.
- **Min rating** (`openrating` → `setrating:<0-10>`, 0 = off) — **premium-gated twice**: the picker won't open without an active subscription, and the setter re-checks server-side because a stale keyboard can outlive an expired subscription. The label reads "premium only" for free users.
- **Language** (`openlang` → `setlang:<code>`, 22 locales shown by native name) — an explicit pick is permanent: the setter passes `language=None` to `RegisterUserUseCase` so the Telegram client code never overwrites it, and the confirmation renders in the freshly-picked locale.
- **Notifications** (`togglenotify`) — flips the daily-broadcast opt-in and redraws the card.

### `/premium` → Stars payment

Header shows the current subscription (tier + human "Expires in N days/hours/minutes" via `ngettext`) or the pitch. Tier buttons from `TIER_CATALOG`: Bronze 100 ⭐ / 7 d, Silver 300 ⭐ / 30 d, Gold 1000 ⭐ / 30 d (Silver vs Gold differ in price only — a placeholder for future perks). Then:

1. `buy:<tier>` → `CreatePremiumInvoiceUseCase` creates a PENDING `Transaction` (purpose `"premium:<tier>"`) and sends a Stars invoice (`currency="XTR"`, empty `provider_token`, payload = transaction UUID).
2. `pre_checkout_query` → always `ok=True` (no stock/validation to do).
3. `successful_payment` → `ConfirmPaymentUseCase` flips the transaction to CONFIRMED and stores `telegram_payment_charge_id`; the `PaymentConfirmed` handler activates the tier from `purpose` as a PURCHASE grant. Telegram redelivers `successful_payment` — the second delivery raises `InvalidStatusTransition`, which the handler deliberately swallows before re-reading premium state, so the user gets the same confirmation twice rather than an error.
4. Confirmation: "✅ Premium activated!" + expiry + pointer to /settings' min-rating filter.

Subscriptions are an **append-only ledger of grants** (purchase / welcome bonus / referral bonus can coexist); "is premium" is derived from the active set at read time — nothing ever mutates or deletes a grant except refund revocation.

### `/my_ratings`

The paid value proposition: *who* rated you. No subscription → `PremiumRequired` → upsell pointing at /premium. Otherwise the last 10 incoming ratings, newest first: `⭐ score/10 — contact, dd.mm hh:mm`. Raters are identified by **User data only** (`@username` linking to `t.me/<username>`; accounts without a handle render as a localized "Anonymous" over a `tg://user?id=…` mention, which resolves because the rater has used this bot) — the use case deliberately never touches the Profile context, since raters aren't required to have a profile. Also reachable via the `show_my_ratings` button shown on /premium to active subscribers.

### `/refer`

Russian-only by product decision (hardcoded strings, own pluralizer, `ruff: noqa: RUF001`). Shows `t.me/<bot>?start=<telegram_id>` plus stats (invitations, registrations, count-to-next-milestone). Reward flow: the pending `Referral` created at the referee's /start is paid out by `ReferralRewardService.mark_profile_created` when the referee **creates a profile** — +1 day premium to both sides, and every 3rd rewarded referral gives the referrer +3 bonus days on top. Idempotent (`mark_rewarded` won't double-pay); a banned referrer is skipped while the referee still gets paid. ⚠️ The message copy says "за каждую регистрацию" — it overpromises; payout actually requires profile creation.

### Daily broadcast (18:00 UTC, taskiq)

The re-engagement loop: "N new profiles" push to everyone with a visible profile, minus banned / notifications-off / those for whom every new profile is their own. Full mechanics under Background tasks.

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
