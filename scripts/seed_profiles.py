"""Seed fake female profiles into the local DB, distributed across cities.

Pipeline is streaming — each iteration:
  1. Picks the next image URL from a pool fetched lazily from Unsplash search.
  2. Downloads image bytes, sends them to OWNER_CHAT_ID via the bot, captures
     the Telegram file_id from the reply.
  3. Creates a User + Profile via CreateProfileUseCase, with the location
     scattered around the city assigned to this index.

Re-runs are safe: each profile uses a deterministic telegram_id
(9_000_000_000 + index); if that user already exists the step is skipped.

Run (note the env -i wrapper from CLAUDE.md):

  env -i HOME="$HOME" \
    PATH="/Users/vasiliikletkin/.pyenv/versions/3.13.11/bin:/usr/bin:/bin" \
    UNSPLASH_ACCESS_KEY="<your key>" \
    /Users/vasiliikletkin/.pyenv/versions/3.13.11/bin/poetry run \
    python -m scripts.seed_profiles --owner-chat-id 877916659

Get an Unsplash access key at https://unsplash.com/developers (free, ~5 min).
Demo access has a 50-requests/hour limit on api.unsplash.com — search uses
per_page=30, so 1000 photos needs ~34 search calls. Image bytes downloaded
from images.unsplash.com do NOT count toward that limit.

Cleanup later (cascade should remove profiles + ratings if the FKs are
configured ON DELETE CASCADE; otherwise delete profiles first):

  DELETE FROM users WHERE telegram_id >= 9000000000;
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import random
import sys
from datetime import UTC, datetime
from typing import Any

import aiohttp
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BufferedInputFile
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from scripts.bio_data import BIO_CTAS, BIO_TEMPLATES
from scripts.name_data import FEMALE_NAMES
from src.application.profile.create_profile import CreateProfileUseCase
from src.application.profile.dto import CreateProfileRequest
from src.domain.identity.entities import User
from src.domain.identity.value_objects import TelegramId
from src.domain.referral.services import ReferralRewardService
from src.infrastructure.config import get_settings
from src.infrastructure.db.repositories.profile import ProfileRepository
from src.infrastructure.db.repositories.referral import ReferralRepository
from src.infrastructure.db.repositories.subscription import SubscriptionRepository
from src.infrastructure.db.repositories.user import UserRepository
from src.infrastructure.db.uow import SqlAlchemyUnitOfWork

log = logging.getLogger("seed")


# --- distribution -----------------------------------------------------------

SEED_TELEGRAM_ID_BASE = 9_000_000_000  # above any real Telegram user id

# (name, latitude, longitude). Indexes 0..99 → city 0, 100..199 → city 1, etc.
CITIES: list[tuple[str, float, float]] = [
    ("Moscow", 55.7558, 37.6173),
    ("Saint Petersburg", 59.9311, 30.3609),
    ("Novosibirsk", 55.0084, 82.9357),
    ("Yekaterinburg", 56.8389, 60.6057),
    ("Kazan", 55.7887, 49.1221),
    ("Nizhny Novgorod", 56.2965, 43.9361),
    ("Chelyabinsk", 55.1644, 61.4368),
    ("Samara", 53.1959, 50.1008),
    ("Rostov-on-Don", 47.2225, 39.7188),
    ("Krasnodar", 45.0355, 38.9753),
]
PROFILES_PER_CITY = 100
CITY_RADIUS_KM = 30.0


def _city_for_index(idx: int) -> tuple[str, float, float]:
    return CITIES[idx // PROFILES_PER_CITY]


def _location_around(lat0: float, lon0: float) -> tuple[float, float]:
    # 1 degree of lat ≈ 111 km; 1 degree of lon shrinks with cos(lat).
    import math

    lat_range = CITY_RADIUS_KM / 111.0
    lon_range = CITY_RADIUS_KM / (111.0 * max(math.cos(math.radians(lat0)), 0.1))
    lat = lat0 + random.uniform(-lat_range, lat_range)
    lon = lon0 + random.uniform(-lon_range, lon_range)
    return (lat, lon)


# --- fake data --------------------------------------------------------------
# Names are pre-generated and stored in scripts/name_data.py (FEMALE_NAMES).
# To regenerate, run: poetry run python -m scripts.gen_names


# How a bio is chosen for a profile. Sum should be 1.0.
# BIO_CTAS and BIO_TEMPLATES live in scripts/bio_data.py (~870 entries).
BIO_EMPTY_PROBABILITY = 0.18
BIO_CTA_PROBABILITY = 0.27
# Remaining ~0.55 → full template.


def _random_bio() -> str:
    r = random.random()
    if r < BIO_EMPTY_PROBABILITY:
        return ""
    if r < BIO_EMPTY_PROBABILITY + BIO_CTA_PROBABILITY:
        return random.choice(BIO_CTAS)
    return random.choice(BIO_TEMPLATES)


def _random_age() -> int:
    """50% in [18,24], 50% in [25,29]."""
    if random.random() < 0.5:
        return random.randint(18, 24)
    return random.randint(25, 29)


# --- Unsplash photo pool ----------------------------------------------------

UNSPLASH_API = "https://api.unsplash.com/search/photos"
# Multiple queries → more diverse faces and avoids saturating one search's
# pagination (Unsplash relevance drops off fast past ~5 pages of one query).
UNSPLASH_QUERIES = [
    "woman portrait",
    "girl portrait",
    "young woman face",
    "female portrait",
    "woman smile",
    "woman headshot",
]


class UnsplashPool:
    """Lazy generator of unique Unsplash image URLs.

    Walks (query, page) combinations, deduping by photo id. Yields the
    ``urls.regular`` URL (≈1080px wide) — Telegram downscales further.
    """

    def __init__(self, http: aiohttp.ClientSession, access_key: str) -> None:
        self._http = http
        self._access_key = access_key
        self._seen: set[str] = set()
        self._queue: list[str] = []
        # (query_idx, page) cursor; page is 1-based per Unsplash docs.
        self._query_idx = 0
        self._page = 1

    async def next_url(self) -> str | None:
        if not self._queue:
            await self._refill()
        if not self._queue:
            return None
        return self._queue.pop(0)

    async def _refill(self) -> None:
        for _ in range(len(UNSPLASH_QUERIES) * 6):  # ~6 pages per query before giving up
            query = UNSPLASH_QUERIES[self._query_idx]
            page = self._page
            params: dict[str, str | int] = {
                "query": query,
                "per_page": 30,
                "page": page,
                "orientation": "portrait",
                "content_filter": "high",
            }
            headers = {"Authorization": f"Client-ID {self._access_key}"}
            try:
                async with self._http.get(
                    UNSPLASH_API,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as r:
                    if r.status == 403:
                        body = await r.text()
                        log.error("Unsplash 403 (rate limit?): %s", body[:200])
                        await asyncio.sleep(60)
                        return
                    r.raise_for_status()
                    payload: dict[str, Any] = await r.json()
            except Exception as exc:
                log.warning("Unsplash search failed (q=%r p=%d): %s", query, page, exc)
                self._advance_cursor()
                continue

            results = payload.get("results", []) or []
            log.info(
                "Unsplash: q=%r p=%d got %d results", query, page, len(results)
            )

            for item in results:
                photo_id = item.get("id")
                url = (item.get("urls") or {}).get("regular")
                if not photo_id or not url:
                    continue
                if photo_id in self._seen:
                    continue
                self._seen.add(photo_id)
                self._queue.append(url)

            self._advance_cursor()
            if self._queue:
                return

    def _advance_cursor(self) -> None:
        self._query_idx += 1
        if self._query_idx >= len(UNSPLASH_QUERIES):
            self._query_idx = 0
            self._page += 1


async def _download_image(http: aiohttp.ClientSession, url: str) -> bytes:
    async with http.get(url, timeout=aiohttp.ClientTimeout(total=60)) as r:
        r.raise_for_status()
        return await r.read()


# --- per-profile pipeline ---------------------------------------------------


async def _process_one(
    *,
    idx: int,
    name: str,
    http: aiohttp.ClientSession,
    pool: UnsplashPool,
    bot: Bot,
    owner_chat_id: int,
    session_factory: async_sessionmaker[AsyncSession],
) -> bool:
    """Create one User + Profile. Returns True on success, False on skip/fail."""
    tg_id = SEED_TELEGRAM_ID_BASE + idx

    # Fast existence check (separate session — closed before the slow work).
    async with session_factory() as session:
        existing = await UserRepository(session=session).get_by_telegram_id(
            TelegramId(tg_id)
        )
    if existing is not None:
        return False

    # 1. URL from the lazy Unsplash pool.
    url = await pool.next_url()
    if url is None:
        log.error("Unsplash pool exhausted at idx=%d", idx)
        raise RuntimeError("photo pool exhausted")

    # 2. Image bytes.
    for attempt in range(3):
        try:
            image_bytes = await _download_image(http, url)
            break
        except Exception as exc:
            log.warning("image download attempt %d for idx=%d: %s", attempt + 1, idx, exc)
            await asyncio.sleep(1.5 * (attempt + 1))
    else:
        log.error("Giving up on image for idx=%d", idx)
        return False

    # 3. Send to bot owner chat to obtain file_id.
    try:
        msg = await bot.send_photo(
            chat_id=owner_chat_id,
            photo=BufferedInputFile(image_bytes, filename=f"face_{idx}.jpg"),
        )
    except Exception as exc:
        log.error("send_photo failed for idx=%d: %s", idx, exc)
        return False
    if not msg.photo:
        log.error("Telegram returned message without photo sizes for idx=%d", idx)
        return False
    file_id = msg.photo[-1].file_id

    # 4. Create User + Profile in one transaction.
    city_name, city_lat, city_lon = _city_for_index(idx)
    async with session_factory() as session:
        user_repo = UserRepository(session=session)
        now = datetime.now(UTC)
        user = User.register(telegram_id=TelegramId(tg_id), now=now, language="ru")
        await user_repo.add(user)

        profile_repo = ProfileRepository(session=session)
        uow = SqlAlchemyUnitOfWork(session=session)
        # Seed users have no PENDING referrals so the service short-circuits;
        # we still need to wire it because the use case requires it.
        referral_service = ReferralRewardService(
            referral_repo=ReferralRepository(session=session),
            user_repo=user_repo,
            subscription_repo=SubscriptionRepository(session=session),
        )
        use_case = CreateProfileUseCase(
            profile_repo=profile_repo,
            referral_service=referral_service,
            uow=uow,
        )

        await use_case.execute(
            CreateProfileRequest(
                owner_id=user.id.value,
                name=name,
                age=_random_age(),
                gender="female",
                bio=_random_bio(),
                photo_file_ids=(file_id,),
                location=_location_around(city_lat, city_lon),
            )
        )

    if idx % 25 == 0:
        log.info("idx=%d city=%s ok", idx, city_name)
    return True


# --- entrypoint -------------------------------------------------------------


async def amain(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    access_key = args.unsplash_key or os.environ.get("UNSPLASH_ACCESS_KEY")
    if not access_key:
        log.error("Provide UNSPLASH_ACCESS_KEY env var or --unsplash-key.")
        return 2

    full_total = len(CITIES) * PROFILES_PER_CITY
    total = min(full_total, args.limit) if args.limit else full_total
    log.info(
        "Target: %d profiles (full plan: %d cities x %d each = %d)",
        total,
        len(CITIES),
        PROFILES_PER_CITY,
        full_total,
    )

    settings = get_settings()
    engine = create_async_engine(settings.postgres.dsn)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    bot = Bot(
        token=settings.bot.token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    created = 0
    skipped = 0
    failed = 0

    if len(FEMALE_NAMES) < total:
        log.error(
            "Static name pool has %d entries but %d profiles requested. "
            "Regenerate with: poetry run python -m scripts.gen_names --count %d",
            len(FEMALE_NAMES),
            total,
            total,
        )
        return 2
    name_pool = FEMALE_NAMES
    log.info(
        "Name pool: %d names available, %d with surname",
        len(name_pool),
        sum(1 for n in name_pool if " " in n),
    )

    try:
        async with aiohttp.ClientSession() as http:
            pool = UnsplashPool(http, access_key)
            for idx in range(total):
                try:
                    ok = await _process_one(
                        idx=idx,
                        name=name_pool[idx],
                        http=http,
                        pool=pool,
                        bot=bot,
                        owner_chat_id=args.owner_chat_id,
                        session_factory=session_factory,
                    )
                except Exception as exc:
                    log.exception("idx=%d crashed: %s", idx, exc)
                    failed += 1
                    continue

                if ok:
                    created += 1
                else:
                    # Distinguish "already there" from "image/send failed" using
                    # a cheap re-check. In practice this branch is rare.
                    async with session_factory() as session:
                        existing = await UserRepository(
                            session=session
                        ).get_by_telegram_id(TelegramId(SEED_TELEGRAM_ID_BASE + idx))
                    if existing is not None:
                        skipped += 1
                    else:
                        failed += 1

                # Keep send_photo under Telegram's per-chat soft limit.
                await asyncio.sleep(0.35)
    finally:
        await bot.session.close()
        await engine.dispose()

    log.info(
        "Done. created=%d skipped=%d failed=%d (target=%d)",
        created,
        skipped,
        failed,
        total,
    )
    return 0 if failed == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed female profiles distributed across cities."
    )
    parser.add_argument(
        "--owner-chat-id",
        type=int,
        required=True,
        help="Telegram chat id where the bot will send photos to obtain file_ids.",
    )
    parser.add_argument(
        "--unsplash-key",
        type=str,
        default=None,
        help="Unsplash API access key. Falls back to $UNSPLASH_ACCESS_KEY.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap total profiles to seed (handy for smoke-testing on N).",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(amain(args)))


if __name__ == "__main__":
    main()
