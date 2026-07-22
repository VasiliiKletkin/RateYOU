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
    target_dir: Path,
    count: int,
    overwrite: bool,
) -> int:
    """Download up to ``count`` photos of ``username`` into ``target_dir``."""
    target_dir.mkdir(parents=True, exist_ok=True)

    if not overwrite and _existing_images(target_dir) >= count:
        print(f"  {username}: already has {count}+ images, skipping")
        return 0

    profile = instaloader.Profile.from_username(loader.context, username)
    if profile.is_private:
        print(f"  {username}: private account, skipping")
        return 0

    saved = 0
    for post in profile.get_posts():
        for url in _image_urls(post, needed=count - saved):
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
    parser.add_argument("usernames", nargs="+", help="Instagram usernames (without @)")
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
        help="First number used in the NNNN_username folder names",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=5.0,
        help="Seconds to sleep between accounts, to stay under rate limits",
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

    total = 0
    for offset, username in enumerate(args.usernames):
        index = args.start_index + offset
        target_dir = args.out_dir / f"{index:04d}_{username}"
        print(f"{username} -> {target_dir}")
        try:
            total += download_profile(loader, username, target_dir, args.count, args.overwrite)
        except instaloader.exceptions.ProfileNotExistsException:
            print(f"  {username}: no such profile")
        except instaloader.exceptions.InstaloaderException as exc:
            print(f"  {username}: failed ({exc})")
        if args.delay and offset < len(args.usernames) - 1:
            time.sleep(args.delay)

    print(f"Done: {total} photo(s) downloaded into {args.out_dir}")


if __name__ == "__main__":
    main()
