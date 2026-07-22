"""Download the last N photos of public Instagram accounts into seed folders.

Output layout matches what ``scripts/seed_profiles.py`` expects: one
subdirectory per account, images numbered ``01.jpg``, ``02.jpg``, ...

  scripts/seed_photos/
    0001_anna/
      01.jpg
      ...
    0002_kate/
      01.jpg

Videos and video sidecar slides are skipped; only still images count toward
the requested number.

Requires ``instaloader`` (not a project dependency -- install it into the
env yourself):

  poetry run pip install instaloader

Run (note the env -i wrapper from CLAUDE.md):

  env -i HOME="$HOME" \
    PATH="/Users/vasiliikletkin/.pyenv/versions/3.13.11/bin:/usr/bin:/bin" \
    /Users/vasiliikletkin/.pyenv/versions/3.13.11/bin/poetry run \
    python -m scripts.fetch_instagram_photos anna kate \
    --out-dir scripts/seed_photos \
    --count 6

Anonymous access is heavily rate-limited by Instagram. If you hit
401/429, log in once in a terminal::

  poetry run instaloader --login YOUR_LOGIN   # stores a session file

then pass ``--login YOUR_LOGIN`` here to reuse that session.

Only fetch accounts you are allowed to use. Scraping Instagram is against
their ToS; this is meant for your own accounts / test data.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

try:
    import instaloader
except ImportError:  # pragma: no cover - dev-only script
    sys.exit("instaloader is not installed. Run: poetry run pip install instaloader")


IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def _normalize_username(raw: str) -> str:
    """Accept ``anna``, ``@anna`` or a profile URL and return ``anna``."""
    value = raw.strip().rstrip("/")
    if "instagram.com" in value:
        value = value.split("instagram.com", 1)[1].lstrip("/")
        value = value.split("?", 1)[0].split("/", 1)[0]
    return value.lstrip("@")


def _slugify(value: str) -> str:
    """Turn a display name into something safe for a directory name."""
    cleaned = "".join(ch if ch.isalnum() or ch in " -_" else " " for ch in value)
    return "_".join(cleaned.split())


def _folder_name(profile: instaloader.Profile, index: int, style: str) -> str:
    """Build the per-profile directory name for the chosen naming style."""
    name = _slugify(profile.full_name or "") or profile.username
    return {
        "index_username": f"{index:04d}_{profile.username}",
        "index_name": f"{index:04d}_{name}",
        "username": profile.username,
        "name": name,
    }[style]


def _image_urls(post: instaloader.Post, needed: int) -> list[str]:
    """Return still-image URLs from a post, at most ``needed`` of them."""
    if post.typename == "GraphSidecar":
        urls = [node.display_url for node in post.get_sidecar_nodes() if not node.is_video]
    elif post.is_video:
        urls = []
    else:
        urls = [post.url]
    return urls[:needed]


def _existing_images(directory: Path) -> int:
    return sum(1 for p in directory.iterdir() if p.suffix.lower() in IMAGE_EXTS)


def download_profile(
    loader: instaloader.Instaloader,
    username: str,
    out_dir: Path,
    index: int,
    folder_style: str,
    count: int,
    delay: float,
    overwrite: bool,
) -> int:
    """Download up to ``count`` photos of ``username`` under ``out_dir``."""
    profile = instaloader.Profile.from_username(loader.context, username)

    target_dir = out_dir / _folder_name(profile, index, folder_style)
    print(f"  {username}: {profile.full_name or '(no name)'} -> {target_dir}")
    target_dir.mkdir(parents=True, exist_ok=True)

    if not overwrite and _existing_images(target_dir) >= count:
        print(f"  {username}: already has {count}+ images, skipping")
        return 0

    if profile.is_private:
        print(f"  {username}: private account, skipping")
        return 0

    saved = 0
    for post in profile.get_posts():
        for url in _image_urls(post, needed=count - saved):
            if saved and delay:
                time.sleep(delay)
            saved += 1
            stem = target_dir / f"{saved:02d}"
            loader.download_pic(filename=str(stem), url=url, mtime=post.date_utc)
            print(f"  {username}: {saved}/{count} <- {post.shortcode}")
            if saved >= count:
                return saved
        if saved >= count:
            break
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "usernames",
        nargs="+",
        help="Instagram usernames, @handles or profile URLs",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("scripts/seed_photos"),
        help="Root directory for the per-account subfolders",
    )
    parser.add_argument("--count", type=int, default=6, help="Photos per account (default 6)")
    parser.add_argument(
        "--login",
        default=None,
        help="Instagram login whose saved session should be reused",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=1,
        help="First number used in the numbered folder names",
    )
    parser.add_argument(
        "--folder-name",
        choices=("index_username", "index_name", "username", "name"),
        default="index_username",
        help=(
            "Per-profile folder naming: 0001_username (default), "
            "0001_Display_Name, username, or Display_Name. Falls back to the "
            "username when the account has no display name."
        ),
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=5.0,
        help="Seconds to sleep between photos and between accounts",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-download even if the folder already holds enough images",
    )
    args = parser.parse_args()

    loader = instaloader.Instaloader(
        quiet=True,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
    )
    if args.login:
        try:
            loader.load_session_from_file(args.login)
        except FileNotFoundError:
            sys.exit(
                f"No saved session for {args.login!r}. "
                f"Run: poetry run instaloader --login {args.login}"
            )

    usernames = [_normalize_username(raw) for raw in args.usernames]
    if not all(usernames):
        sys.exit("Could not parse a username out of every argument")

    total = 0
    for offset, username in enumerate(usernames):
        index = args.start_index + offset
        print(f"{username}")
        try:
            total += download_profile(
                loader,
                username,
                args.out_dir,
                index,
                args.folder_name,
                args.count,
                args.delay,
                args.overwrite,
            )
        except instaloader.exceptions.ProfileNotExistsException:
            if args.login:
                print(f"  {username}: no such profile")
            else:
                print(
                    f"  {username}: not reachable anonymously (Instagram returns 403). "
                    f"Log in once with `poetry run instaloader --login YOUR_LOGIN`, "
                    f"then re-run with --login YOUR_LOGIN"
                )
        except instaloader.exceptions.InstaloaderException as exc:
            print(f"  {username}: failed ({exc})")
        if args.delay and offset < len(args.usernames) - 1:
            time.sleep(args.delay)

    print(f"Done: {total} photo(s) downloaded into {args.out_dir}")


if __name__ == "__main__":
    main()
