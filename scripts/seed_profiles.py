"""Seed fake female profiles into the local DB, distributed across cities.

Photos come from a local directory you prepare yourself. Each immediate
subdirectory under ``--photos-dir`` becomes one profile; image files inside
(jpg/jpeg/png/webp, 1-6 per folder) become the profile's photos. Subdirs are
processed in alphanumeric order, so the first sorted subdir is profile idx 0.

Pipeline per profile:
  1. Read up to 6 image files from the next subdirectory.
  2. Upload each via the bot to OWNER_CHAT_ID, capture Telegram file_id.
  3. Create User + Profile in one transaction.

Re-runs are safe: each profile uses a deterministic telegram_id
(9_000_000_000 + index); if that user already exists the step is skipped.

Expected layout::

  scripts/seed_photos/
    0001_anna/
      01.jpg
      02.jpg
      03.jpg
    0002_kate/
      front.jpg
      beach.webp
    ...

Run (note the env -i wrapper from CLAUDE.md):

  env -i HOME="$HOME" \
    PATH="/Users/vasiliikletkin/.pyenv/versions/3.13.11/bin:/usr/bin:/bin" \
    /Users/vasiliikletkin/.pyenv/versions/3.13.11/bin/poetry run \
    python -m scripts.seed_profiles \
    --owner-chat-id 877916659 \
    --photos-dir scripts/seed_photos \
    --city Kazan \
    --limit 5

``--city`` geocodes one place through Nominatim and scatters every profile
around it, 10 m to 1 km out by default (``--spread-min-m`` /
``--spread-max-m``). Without it, profiles are spread across the built-in
CITIES table instead, PROFILES_PER_CITY per city.

Cleanup later (cascade should remove profiles + ratings if the FKs are
configured ON DELETE CASCADE; otherwise delete profiles first):

  DELETE FROM users WHERE telegram_id >= 9000000000;
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

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
from src.domain.identity.value_objects import Language, Role, TelegramId
from src.domain.profile.exceptions import GeocodingUnavailable, InvalidLocation
from src.domain.referral.services import ReferralRewardService
from src.infrastructure.config import get_settings
from src.infrastructure.db.repositories.profile import ProfileRepository
from src.infrastructure.db.repositories.referral import ReferralRepository
from src.infrastructure.db.repositories.subscription import SubscriptionRepository
from src.infrastructure.db.repositories.user import UserRepository
from src.infrastructure.db.uow import SqlAlchemyUnitOfWork
from src.infrastructure.geocoding.nominatim import NominatimGeocoder

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


METERS_PER_DEGREE_LAT = 111_320.0


def _location_near(
    lat0: float,
    lon0: float,
    min_meters: float,
    max_meters: float,
) -> tuple[float, float]:
    """Offset a point by a random bearing and distance in [min, max] metres.

    Distance is uniform in metres rather than in area, so the profiles are
    spread evenly across the range instead of piling up near the outer edge.
    """
    distance = random.uniform(min_meters, max_meters)
    bearing = random.uniform(0.0, 2.0 * math.pi)
    north = distance * math.cos(bearing)
    east = distance * math.sin(bearing)
    # 1 degree of lat is ~constant; 1 degree of lon shrinks with cos(lat).
    lat = lat0 + north / METERS_PER_DEGREE_LAT
    lon = lon0 + east / (METERS_PER_DEGREE_LAT * max(math.cos(math.radians(lat0)), 0.01))
    return (lat, lon)


async def _geocode_city(query: str) -> tuple[str, float, float]:
    """Resolve a city name to (label, lat, lon). Raises on no match."""
    settings = get_settings()
    geocoder = NominatimGeocoder(
        base_url=settings.geocoding.base_url,
        user_agent=settings.geocoding.user_agent,
        timeout_seconds=settings.geocoding.timeout_seconds,
    )
    candidates = await geocoder.geocode(query, language="ru", limit=5)
    if not candidates:
        raise RuntimeError(f"Geocoder found nothing for {query!r}")
    if len(candidates) > 1:
        log.info("Other matches for %r: %s", query, [c.label for c in candidates[1:]])
    best = candidates[0]
    return (best.label, best.location.lat, best.location.lon)


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


# --- local photo source -----------------------------------------------------

# Telegram's send_photo accepts these formats and downscales them.
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_PHOTOS_PER_PROFILE = 6  # matches src.domain.profile.value_objects.Photos.MAX_COUNT


class LocalPhotoSource:
    """Maps a profile index to a list of local image file paths.

    Layout convention (under ``--photos-dir``)::

        photos_dir/
          0001_anna/          # name doesn't matter, only sort order does
            01.jpg
            02.jpg
          0002_kate/
            front.jpg
            beach.webp
            cafe.png
          ...

    Each immediate subdirectory becomes one profile. Subdirectories are
    enumerated in alphanumeric order, so profile idx 0 is the first one.
    Photo files inside are also sorted, capped at MAX_PHOTOS_PER_PROFILE.
    """

    def __init__(self, root: Path) -> None:
        if not root.is_dir():
            raise FileNotFoundError(f"Photos directory not found: {root}")
        self._profile_dirs: list[Path] = sorted(
            (p for p in root.iterdir() if p.is_dir()),
            key=lambda p: p.name,
        )
        if not self._profile_dirs:
            raise RuntimeError(f"No profile subdirectories in {root}")

    def __len__(self) -> int:
        return len(self._profile_dirs)

    def photos_for(self, idx: int) -> list[Path]:
        """Return up to ``MAX_PHOTOS_PER_PROFILE`` image paths for profile idx."""
        if idx >= len(self._profile_dirs):
            return []
        profile_dir = self._profile_dirs[idx]
        files = sorted(
            f for f in profile_dir.iterdir()
            if f.is_file() and f.suffix.lower() in PHOTO_EXTENSIONS
        )
        return files[:MAX_PHOTOS_PER_PROFILE]


# --- per-profile pipeline ---------------------------------------------------


async def _upload_photo(
    bot: Bot,
    owner_chat_id: int,
    path: Path,
) -> str | None:
    """Upload one local image to the owner chat, return its file_id."""
    image_bytes = await asyncio.to_thread(path.read_bytes)
    try:
        msg = await bot.send_photo(
            chat_id=owner_chat_id,
            photo=BufferedInputFile(image_bytes, filename=path.name),
        )
    except Exception as exc:
        log.error("send_photo failed for %s: %s", path, exc)
        return None
    if not msg.photo:
        log.error("Telegram returned message without photo sizes: %s", path)
        return None
    return msg.photo[-1].file_id


async def _process_one(
    *,
    idx: int,
    name: str,
    city: tuple[str, float, float],
    spread_meters: tuple[float, float],
    photo_paths: list[Path],
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

    if not photo_paths:
        log.warning("idx=%d has no photos, skipping", idx)
        return False

    # 1. Upload each photo, collect file_ids.
    file_ids: list[str] = []
    for path in photo_paths:
        fid = await _upload_photo(bot, owner_chat_id, path)
        if fid is None:
            log.error("idx=%d: photo upload failed for %s — skipping profile", idx, path)
            return False
        file_ids.append(fid)
        await asyncio.sleep(0.35)  # stay under per-chat soft rate-limit

    # 2. Create User + Profile in one transaction.
    city_name, city_lat, city_lon = city
    async with session_factory() as session:
        user_repo = UserRepository(session=session)
        now = datetime.now(UTC)
        user = User.register(
            telegram_id=TelegramId(tg_id),
            now=now,
            language=Language.RU,
            role=Role.SEED,
        )
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
                photo_file_ids=tuple(file_ids),
                location=_location_near(city_lat, city_lon, *spread_meters),
            )
        )

    log.info("idx=%d city=%s photos=%d ok", idx, city_name, len(file_ids))
    return True


# --- entrypoint -------------------------------------------------------------


async def amain(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        photo_source = LocalPhotoSource(args.photos_dir)
    except (FileNotFoundError, RuntimeError) as exc:
        log.error("%s", exc)
        return 2

    if args.spread_min_m > args.spread_max_m:
        log.error("--spread-min-m must not exceed --spread-max-m")
        return 2
    spread = (args.spread_min_m, args.spread_max_m)

    # --city pins every profile to one geocoded point; without it the built-in
    # CITIES table is used, PROFILES_PER_CITY profiles per city in order.
    pinned_city: tuple[str, float, float] | None = None
    if args.city:
        try:
            pinned_city = await _geocode_city(args.city)
        except (RuntimeError, GeocodingUnavailable, InvalidLocation) as exc:
            log.error("Could not geocode %r: %s", args.city, exc)
            return 2
        log.info(
            "City %r resolved to %s (%.5f, %.5f)",
            args.city,
            pinned_city[0],
            pinned_city[1],
            pinned_city[2],
        )

    full_total = (
        len(photo_source) if pinned_city else len(CITIES) * PROFILES_PER_CITY
    )
    available = len(photo_source)
    total = min(full_total, available)
    if args.limit:
        total = min(total, args.limit)
    log.info(
        "Target: %d profiles (photo dirs: %d, full plan: %d), spread %.0f-%.0f m",
        total,
        available,
        full_total,
        args.spread_min_m,
        args.spread_max_m,
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
        for idx in range(total):
            try:
                ok = await _process_one(
                    idx=idx,
                    name=name_pool[idx],
                    city=pinned_city or _city_for_index(idx),
                    spread_meters=spread,
                    photo_paths=photo_source.photos_for(idx),
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
                # Distinguish "already there" from "upload failed / no photos"
                # via a cheap re-check.
                async with session_factory() as session:
                    existing = await UserRepository(
                        session=session
                    ).get_by_telegram_id(TelegramId(SEED_TELEGRAM_ID_BASE + idx))
                if existing is not None:
                    skipped += 1
                else:
                    failed += 1
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
        "--photos-dir",
        type=Path,
        required=True,
        help=(
            "Directory of per-profile subdirectories. Each subdirectory "
            "becomes one profile; image files inside (1-6, jpg/png/webp) "
            "become its photos. Subdirs are processed in alphanumeric order."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap total profiles to seed (handy for smoke-testing on N).",
    )
    parser.add_argument(
        "--city",
        default=None,
        help=(
            "City name to geocode (Nominatim). All profiles are scattered "
            "around that one point. Without it, the built-in 10-city table "
            "is used instead."
        ),
    )
    parser.add_argument(
        "--spread-min-m",
        type=float,
        default=10.0,
        help="Minimum distance from the city centre, in metres (default 10).",
    )
    parser.add_argument(
        "--spread-max-m",
        type=float,
        default=1000.0,
        help="Maximum distance from the city centre, in metres (default 1000).",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(amain(args)))


if __name__ == "__main__":
    main()
