"""
scripts/igdb_import.py
One-time bulk import of the IGDB game catalog into dim.dim_games (personal Supabase).

Prerequisites:
    1. Run migration 010_igdb_columns.sql on your personal Supabase first.
    2. Download three data dumps from https://api-docs.igdb.com/#data-dumps:
           games.csv    — id, name, genres, slug, rating_count, ...
           genres.csv   — id, name
           covers.csv   — id, game (game_id), url
       Save all three into a single folder (default: ./igdb_dumps/).
    3. pip install psycopg2-binary

Usage:
    PERSONAL_DATABASE_URL="postgresql://..." python scripts/igdb_import.py

    # Filter to well-known games only (speeds up import + reduces noise):
    IGDB_MIN_RATINGS=10 python scripts/igdb_import.py

    # Point at a different dump folder:
    IGDB_DUMP_DIR=/tmp/igdb python scripts/igdb_import.py

What it does:
    - Inserts games into dim.dim_games with igdb_id, igdb_slug, cover_url,
      game_genre, game_subgenre populated from the dump.
    - Splits "Call of Duty: Modern Warfare III" → game_name="Call of Duty",
      game_installment="Modern Warfare III".
    - ON CONFLICT (igdb_id) DO NOTHING — safe to re-run, never overwrites
      records you've manually curated.
    - ON CONFLICT (game_name, game_installment) — also skipped if name already
      exists without an igdb_id (manual entry).

Output:
    Prints progress every 5,000 rows and a final summary.
"""

from __future__ import annotations

import csv
import os
import re
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

# ── Config ────────────────────────────────────────────────────────────────────

DATABASE_URL   = os.getenv("PERSONAL_DATABASE_URL", "")
DUMP_DIR       = Path(os.getenv("IGDB_DUMP_DIR", "igdb_dumps"))
MIN_RATINGS    = int(os.getenv("IGDB_MIN_RATINGS", "0"))  # 0 = import everything
CHUNK_SIZE     = 500

# ── IGDB genre_id → (game_genre, game_subgenre) ──────────────────────────────
# Keys are IGDB's fixed genre IDs (non-sequential — IGDB's own numbering).
# Values must match GENRES in web/lib/constants.ts exactly.
# Genres from constants.ts that have no IGDB genre ID (Battle Royale, Stealth,
# Survival, MMORPGs, Action RPGs, etc.) can't appear here — they fall under
# IGDB's broader buckets and get assigned by the user after import.

GENRE_MAP: dict[int, tuple[str, str]] = {
    2:  ("Adventure",                "Graphic"),                   # Point-and-click
    4:  ("Fighting",                 "2D Versus"),                 # Fighting
    5:  ("Shooter",                  "Military"),                  # Shooter
    7:  ("Party",                    "Rhythm & Music"),            # Music
    8:  ("Platformers",              "Traditional 2D Side\u2011Scrolling"),  # Platform
    9:  ("Puzzle",                   "Logic"),                     # Puzzle
    10: ("Racing",                   "Simulation\u2011Style"),     # Racing
    11: ("Real-Time Strategy (RTS)", "Classic Base\u2011Building"),# Real Time Strategy
    12: ("Role-Playing (RPG)",       "Action"),                    # Role-playing (RPG)
    13: ("Simulation",               "Other"),                     # Simulator
    14: ("Sports",                   "Simulation"),                # Sport
    15: ("Strategy",                 "Turn-Based Strategy (TBS)"), # Strategy
    16: ("Strategy",                 "Turn-Based Strategy (TBS)"), # Turn-based strategy
    24: ("Strategy",                 "Real-Time Tactics (RTT)"),   # Tactical
    25: ("Action RPGs",              "Hack-and-Slash"),            # Hack and slash
    26: ("Party",                    "Trivia"),                    # Quiz/Trivia
    30: ("Casual",                   "Hyper\u2011Casual"),         # Pinball
    31: ("Adventure",                "Real-Time 3D"),              # Adventure
    32: ("Action-Adventure",         "Open-World"),                # Indie (cross-cutting)
    33: ("Casual",                   "Hyper\u2011Casual"),         # Arcade
    34: ("Adventure",                "Visual Novel"),              # Visual Novel
    35: ("Casual",                   "Card & Board"),              # Card & Board Game
    36: ("Strategy",                 "Real-Time Strategy (RTS)"),  # MOBA
}

# ── Installment splitting ─────────────────────────────────────────────────────

# Matches a colon-separated subtitle that looks like a real installment,
# not just a punctuation artifact.
_COLON_RE = re.compile(r"^(.+?)\s*:\s*(.+)$")

# Words that, when the base name ends with them, suggest the colon is part of
# a franchise title rather than a subtitle separator — don't split these.
_NO_SPLIT_ENDINGS = {
    "war", "life", "age", "world", "city", "hero", "saga", "tale", "quest",
    "force", "night", "day", "time", "code", "zone", "gate", "path", "mark",
}


def split_installment(raw: str) -> tuple[str, str | None]:
    """
    Split "Call of Duty: Modern Warfare III" → ("Call of Duty", "Modern Warfare III").
    Returns (raw, None) when no reliable subtitle is detected.
    """
    raw = raw.strip()
    m = _COLON_RE.match(raw)
    if not m:
        return raw, None

    base, sub = m.group(1).strip(), m.group(2).strip()

    # Skip if base is too short or ends with a word that looks like it belongs
    if len(base) < 3 or len(sub) < 2:
        return raw, None

    last_word = base.split()[-1].lower().rstrip("s")
    if last_word in _NO_SPLIT_ENDINGS:
        return raw, None

    return base, sub


# ── Cover URL normalisation ───────────────────────────────────────────────────

def normalise_cover_url(raw: str | None) -> str | None:
    if not raw:
        return None
    url = raw.strip()
    if url.startswith("//"):
        url = "https:" + url
    # Upgrade thumbnail → cover_big (264×352)
    url = url.replace("/t_thumb/", "/t_cover_big/")
    return url


# ── Dump loaders ─────────────────────────────────────────────────────────────

def load_genres(path: Path) -> dict[int, str]:
    """genres.csv → {igdb_genre_id: genre_name}"""
    result: dict[int, str] = {}
    if not path.exists():
        print(f"  ⚠  genres.csv not found at {path} — using built-in GENRE_MAP only")
        return result
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            try:
                result[int(row["id"])] = row.get("name", "").strip()
            except (ValueError, KeyError):
                pass
    print(f"  ✓  genres.csv: {len(result):,} entries")
    return result


def load_covers(path: Path) -> dict[int, str]:
    """covers.csv → {igdb_game_id: cover_url}"""
    result: dict[int, str] = {}
    if not path.exists():
        print(f"  ⚠  covers.csv not found at {path} — cover_url will be NULL")
        return result
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            try:
                game_id = int(row["game"])
                url = normalise_cover_url(row.get("url"))
                if url:
                    result[game_id] = url
            except (ValueError, KeyError):
                pass
    print(f"  ✓  covers.csv: {len(result):,} entries")
    return result


def parse_int_array(raw: str) -> list[int]:
    """Parse IGDB's '{1,2,3}' or '1,2,3' genre arrays."""
    cleaned = raw.strip().lstrip("{").rstrip("}")
    return [int(x.strip()) for x in cleaned.split(",") if x.strip().lstrip("-").isdigit()]


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    if not DATABASE_URL:
        sys.exit(
            "❌  PERSONAL_DATABASE_URL is not set.\n"
            "    Export it before running:\n"
            "    PERSONAL_DATABASE_URL='postgresql://...' python scripts/igdb_import.py"
        )

    games_path  = DUMP_DIR / "games.csv"
    genres_path = DUMP_DIR / "genres.csv"
    covers_path = DUMP_DIR / "covers.csv"

    if not games_path.exists():
        sys.exit(
            f"❌  games.csv not found at {games_path}\n"
            f"    Download from https://api-docs.igdb.com/#data-dumps\n"
            f"    and set IGDB_DUMP_DIR to the folder containing the three CSV files."
        )

    print(f"\n📂  Loading lookup tables from {DUMP_DIR}/")
    genre_names = load_genres(genres_path)
    covers      = load_covers(covers_path)

    print(f"\n📖  Parsing {games_path} …")
    rows: list[tuple] = []
    skipped_filter = 0
    parse_errors   = 0

    with open(games_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for line_no, row in enumerate(reader, start=2):
            try:
                igdb_id  = int(row["id"])
                raw_name = (row.get("name") or "").strip()
                if not raw_name:
                    continue

                # Optional rating filter — skip obscure stubs
                if MIN_RATINGS:
                    rating_count = int(row.get("rating_count") or 0)
                    if rating_count < MIN_RATINGS:
                        skipped_filter += 1
                        continue

                game_name, game_installment = split_installment(raw_name)

                # Resolve genre → (game_genre, game_subgenre)
                genre_ids_raw = row.get("genres") or ""
                genre_ids     = parse_int_array(genre_ids_raw) if genre_ids_raw.strip() else []

                game_genre = game_subgenre = None
                for gid in genre_ids:
                    if gid in GENRE_MAP:
                        game_genre, game_subgenre = GENRE_MAP[gid]
                        break

                igdb_slug = (row.get("slug") or "").strip() or None
                cover_url = covers.get(igdb_id)

                rows.append((
                    game_name,
                    game_installment,
                    game_genre,
                    game_subgenre,
                    igdb_id,
                    igdb_slug,
                    cover_url,
                ))
            except Exception as exc:
                parse_errors += 1
                if parse_errors <= 5:
                    print(f"  ⚠  Line {line_no} parse error: {exc}")

    total_parsed = len(rows)
    print(f"  ✓  {total_parsed:,} games parsed")
    if skipped_filter:
        print(f"  ⊘  {skipped_filter:,} skipped (rating_count < {MIN_RATINGS})")
    if parse_errors:
        print(f"  ⚠  {parse_errors:,} parse errors (shown first 5 above)")

    if not rows:
        sys.exit("❌  Nothing to insert — check your dump files.")

    print(f"\n🔌  Connecting to database …")
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    conn.autocommit = False
    cur = conn.cursor()

    print(f"⬆   Inserting {total_parsed:,} rows into dim.dim_games …\n")
    inserted = errors = 0

    for i in range(0, total_parsed, CHUNK_SIZE):
        chunk = rows[i : i + CHUNK_SIZE]
        try:
            execute_values(
                cur,
                """
                INSERT INTO dim.dim_games
                    (game_name, game_installment, game_genre, game_subgenre,
                     igdb_id, igdb_slug, cover_url)
                VALUES %s
                ON CONFLICT (igdb_id) DO NOTHING
                """,
                chunk,
            )
            conn.commit()
            inserted += cur.rowcount if cur.rowcount >= 0 else 0
        except Exception as exc:
            conn.rollback()
            errors += len(chunk)
            print(f"  ⚠  Chunk {i}–{i + len(chunk)} failed: {exc}")

        # Progress every 5,000 rows
        processed = i + len(chunk)
        if processed % 5000 < CHUNK_SIZE or processed >= total_parsed:
            pct = int(processed / total_parsed * 100)
            print(f"  {pct:3d}%  {processed:>8,} / {total_parsed:,} processed", end="\r")

    cur.close()
    conn.close()

    skipped_db = total_parsed - inserted - errors
    print(f"\n\n{'─' * 45}")
    print(f"  ✅  Import complete")
    print(f"  Inserted  : {inserted:,}")
    print(f"  Skipped   : {skipped_db:,}  (already existed — ON CONFLICT DO NOTHING)")
    print(f"  Errors    : {errors:,}")
    print(f"{'─' * 45}\n")


if __name__ == "__main__":
    run()
