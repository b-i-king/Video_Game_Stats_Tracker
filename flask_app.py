# ══════════════════════════════════════════════════════════════════════════════
# SUPABASE MIGRATION REFERENCE — grep targets before going live
# ══════════════════════════════════════════════════════════════════════════════
# Replace ALL of the following Redshift-specific syntax with PostgreSQL:
#
#   GETDATE()                    →  NOW()
#   CONVERT_TIMEZONE('UTC', 'America/Los_Angeles', col)
#                                →  col AT TIME ZONE 'America/Los_Angeles'
#   CAST(CONVERT_TIMEZONE(…) AS DATE)
#                                →  (col AT TIME ZONE 'America/Los_Angeles')::DATE
#   STDDEV_SAMP(x)               →  STDDEV_SAMP(x)  ✅ same in PostgreSQL
#   COUNT(DISTINCT …)            →  COUNT(DISTINCT …) ✅ same
#   ISNULL(x, y)                 →  COALESCE(x, y)  (check if any exist)
#
# As of 2026-03-31 grep counts:  GETDATE x13,  CONVERT_TIMEZONE x11
# Run:  grep -n "GETDATE\|CONVERT_TIMEZONE\|ISNULL" flask_app.py
# ══════════════════════════════════════════════════════════════════════════════

import os
import re
import time
import threading
import psycopg2
import numpy as np
from scipy import stats as scipy_stats
from collections import defaultdict
from psycopg2.pool import SimpleConnectionPool
from flask import Flask, request, jsonify, send_file
from datetime import datetime, timedelta, timezone
import jwt
from flask_cors import CORS
import atexit
from utils.chart_utils import generate_bar_chart, generate_line_chart, get_stat_history_from_db, generate_interactive_chart
from utils.gcs_utils import upload_chart_to_gcs, upload_interactive_chart_to_gcs
from utils.ifttt_utils import trigger_ifttt_post, generate_post_caption
from utils.queue_utils import (
    ensure_post_queue_table, enqueue_post, get_oldest_pending,
    mark_status, get_queue_counts, reset_failed_to_pending,
    reset_stale_processing, purge_old_sent
)

app = Flask(__name__)
CORS(app, origins=[
    "https://video-game-stats-tracking.streamlit.app",  # Streamlit (keep running in parallel)
    "https://video-game-stats-tracker.vercel.app",       # Next.js / Vercel
    "http://localhost:3000",                              # Next.js local dev
    "http://localhost:8501",                              # Streamlit local dev
])

# ---------------------------------------------------------------------------
# Lightweight in-memory response cache (no extra dependencies)
# Keys: str  →  (response_dict, status_code, expires_at_monotonic)
# ---------------------------------------------------------------------------
_endpoint_cache: dict = {}

# ---------------------------------------------------------------------------
# OBS Active flag — controls whether OBS overlay endpoints hit Redshift.
# Set to True via /api/set_obs_active when streaming/recording, False otherwise.
# Resets to False on app restart (safe default — no spurious queries).
# ---------------------------------------------------------------------------
obs_active: bool = False

def _cache_get(key):
    """Return (data_dict, status_code) if a fresh entry exists, else None."""
    entry = _endpoint_cache.get(key)
    if entry and time.monotonic() < entry[2]:
        return entry[0], entry[1]
    _endpoint_cache.pop(key, None)
    return None

def _cache_set(key, data, status_code, ttl_seconds):
    """Store a response dict with a TTL."""
    _endpoint_cache[key] = (data, status_code, time.monotonic() + ttl_seconds)

def _cache_invalidate_obs():
    """Clear all OBS-related cached responses (called after new stats are saved)."""
    for k in list(_endpoint_cache.keys()):
        if k.startswith(('dash_', 'ticker_')):
            _endpoint_cache.pop(k, None)

# ---------------------------------------------------------------------------
# Lightweight user record cache — avoids a Redshift round-trip on repeat logins.
# Keys: user_email  →  (user_id, is_trusted, expires_at_monotonic)
# ---------------------------------------------------------------------------
_user_cache: dict = {}

def _user_cache_get(email: str):
    entry = _user_cache.get(email)
    if entry and time.monotonic() < entry[2]:
        return entry[0], entry[1]  # (user_id, is_trusted)
    _user_cache.pop(email, None)
    return None

def _user_cache_set(email: str, user_id, is_trusted: bool, ttl: int = 300):
    _user_cache[email] = (user_id, is_trusted, time.monotonic() + ttl)

# ──────────────────────────────────────────────────────────────────────────────
# CONTENT SAFETY & RATE LIMITING
# ──────────────────────────────────────────────────────────────────────────────
try:
    from better_profanity import profanity as _profanity
    _profanity.load_censor_words()
    _PROFANITY_AVAILABLE = True
except ImportError:
    _PROFANITY_AVAILABLE = False
    print("⚠️  better-profanity not installed — profanity checks skipped")

# Stat type: letters, numbers, spaces, hyphens only (1–50 chars)
_STAT_TYPE_RE = re.compile(r'^[A-Za-z0-9 \-]{1,50}$')
# Player/game name: letters, numbers, spaces, hyphens, underscores, periods (1–100 chars)
_NAME_RE = re.compile(r'^[A-Za-z0-9 _\-\.]{1,100}$')

# Free tier limits
MAX_FREE_PLAYERS = 2

def _content_check(value: str, field: str, pattern=None):
    """Returns (error_dict, 400) if value fails content checks, else None."""
    if not value or not value.strip():
        return {"error": f"'{field}' cannot be empty."}, 400
    if pattern and not pattern.match(value.strip()):
        return {"error": f"'{field}' contains invalid characters."}, 400
    if _PROFANITY_AVAILABLE and _profanity.contains_profanity(value):
        return {"error": f"'{field}' contains inappropriate language."}, 400
    return None

def _rate_limit_check(user_email: str, action: str, max_per_hour: int):
    """Returns True if within limit, False if exceeded. Uses in-memory cache."""
    key = f"rl_{action}_{user_email}"
    cached = _cache_get(key)
    count = cached[0].get("n", 0) if cached else 0
    if count >= max_per_hour:
        return False
    _cache_set(key, {"n": count + 1}, 200, ttl_seconds=3600)
    return True

# --- Environment Variable Check ---
DB_URL = os.environ.get("DB_URL")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
API_KEY = os.environ.get("API_KEY") # Still needed for login and add_trusted_user
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
TRUSTED_EMAILS_STR = os.environ.get("TRUSTED_EMAILS", "")
TRUSTED_EMAILS_LIST = [email.strip() for email in TRUSTED_EMAILS_STR.split(',') if email.strip()]
OBS_SECRET_KEY = os.environ.get("OBS_SECRET_KEY")
CRON_SECRET = os.environ.get("CRON_SECRET")

if not all([DB_URL, DB_NAME, DB_USER, DB_PASSWORD, API_KEY, JWT_SECRET_KEY]):
    print("WARNING: One or more environment variables are not set. Using default values.")
if not TRUSTED_EMAILS_LIST:
    print("WARNING: TRUSTED_EMAILS environment variable is not set or empty. No users will be automatically marked as trusted.")
if not CRON_SECRET:
    print("WARNING: CRON_SECRET not set — /api/process_queue will reject all requests.")

# --- Render Postgres (post_queue) setup ---
try:
    ensure_post_queue_table()
    print("✅ post_queue table ready.")
except Exception as _pq_err:
    print(f"⚠️  Could not initialize post_queue table: {_pq_err}")

# --- Database Connection Pool ---
# Create the connection pool once when the app starts
# Global pool variable
db_pool = None

def initialize_db_pool():
    """Initialize the database connection pool (called once)."""
    global db_pool
    
    # Don't reinitialize if pool already exists
    if db_pool is not None:
        print("Database pool already initialized, skipping...")
        return db_pool
    
    try:
        print("Initializing database connection pool...")
        db_pool = SimpleConnectionPool(
            minconn=0,      # Keep low for development
            maxconn=3,     # Reasonable limit
            host=DB_URL,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=5439,
            connect_timeout=30,
            sslmode='require'
        )
        print("✅ Database connection pool initialized successfully.")
        
        # Register cleanup on exit
        atexit.register(close_db_pool)
        
        return db_pool
    except (Exception, psycopg2.Error) as error:
        print(f"❌ FATAL ERROR: Failed to initialize database connection pool: {error}")
        db_pool = None
        return None

def close_db_pool():
    """Close all connections in the pool."""
    global db_pool
    if db_pool:
        try:
            print("Closing database connection pool...")
            db_pool.closeall()
            print("✅ Database pool closed.")
        except Exception as e:
            print(f"⚠️ Error closing pool: {e}")
        finally:
            db_pool = None

def get_db_connection():
    """Gets a connection from the pool."""
    global db_pool
    
    # Initialize pool if it doesn't exist
    if db_pool is None:
        initialize_db_pool()
    
    if db_pool:
        try:
            return db_pool.getconn()
        except (Exception, psycopg2.Error) as error:
            print(f"Error getting connection from pool: {error}")
            return None
    else:
        print("Error: Database pool is not initialized.")
        return None

def release_db_connection(conn, close=True):
    """
    Returns a connection to the pool, or closes it immediately.

    Default close=True: physically closes the connection after each request
    so Redshift Serverless can detect inactivity and auto-pause sooner.
    Pass close=False to return the connection to the pool for reuse
    (faster subsequent requests, but keeps Redshift warm longer).
    """
    global db_pool
    if conn:
        if db_pool:
            # putconn(close=True) closes the connection AND removes it from
            # the pool's internal count — prevents "pool exhausted" errors.
            db_pool.putconn(conn, close=close)
        else:
            try:
                conn.close()
            except Exception:
                pass
        
def create_tables():
    """Creates the necessary database tables if they do not exist."""
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            print("Could not create tables: No database connection.")
            return
        
        cur = conn.cursor()
        print("Creating 'dim' and 'fact' schema and tables if they do not exist...")
        
        # Create the dim and fact schema
        cur.execute("""
            CREATE SCHEMA IF NOT EXISTS dim;
            CREATE SCHEMA IF NOT EXISTS fact;
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dim.dim_users (
                user_id INT IDENTITY(1, 1) PRIMARY KEY,
                user_email VARCHAR(255) NOT NULL UNIQUE,
                is_trusted BOOLEAN NOT NULL DEFAULT FALSE
            );
            
            CREATE TABLE IF NOT EXISTS dim.dim_games (
                game_id INT IDENTITY(1, 1) PRIMARY KEY,
                game_name VARCHAR(255) NOT NULL,
                game_installment VARCHAR(255),
                game_genre VARCHAR(255),
                game_subgenre VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(game_name, game_installment) -- Unique constraint on (Franchise, Installment)
            );

            CREATE TABLE IF NOT EXISTS dim.dim_players (
                player_id INT IDENTITY(1, 1) PRIMARY KEY,
                player_name VARCHAR(255) NOT NULL UNIQUE,
                user_id INTEGER REFERENCES dim.dim_users(user_id) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(player_name, user_id) 
            );
            
            CREATE TABLE IF NOT EXISTS dim.dim_dashboard_state (
                state_id INT PRIMARY KEY DEFAULT 1, -- Only one row
                current_player_id INTEGER,
                current_game_id INTEGER,
                updated_at TIMESTAMP DEFAULT GETDATE()
            );
            
            CREATE TABLE IF NOT EXISTS fact.fact_game_stats (
                stat_id INT IDENTITY(1, 1) PRIMARY KEY,
                game_id INTEGER REFERENCES dim.dim_games(game_id),
                player_id INTEGER REFERENCES dim.dim_players(player_id),
                stat_type VARCHAR(50) NOT NULL,
                stat_value INTEGER,
                game_mode VARCHAR(255),
                solo_mode INTEGER,
                party_size VARCHAR(20),
                game_level INTEGER,
                win INTEGER,
                ranked INTEGER,
                pre_match_rank_value VARCHAR(50),
                post_match_rank_value VARCHAR(50),
                overtime INTEGER NOT NULL DEFAULT 0,
                difficulty VARCHAR(20),
                input_device VARCHAR(30) NOT NULL DEFAULT 'Controller',
                platform VARCHAR(20) NOT NULL DEFAULT 'PC',
                first_session_of_day INTEGER NOT NULL DEFAULT 1,
                was_streaming INTEGER NOT NULL DEFAULT 0,
                played_at TIMESTAMP DEFAULT GETDATE()
            );
        """)
        
        # Ensure the single row exists
        cur.execute("SELECT 1 FROM dim.dim_dashboard_state WHERE state_id = 1;")
        if not cur.fetchone():
            # 2. If it doesn't exist, insert it
            print("Initializing dashboard state row...")
            cur.execute("INSERT INTO dim.dim_dashboard_state (state_id) VALUES (1);")
            conn.commit()
        else:
            print("Dashboard state row already exists.")
        
        conn.commit()
        print("Schema and tables created or already exist.")
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error while creating tables: {error}")
        if conn:
            conn.rollback()
    finally:
        release_db_connection(conn)

# --- Custom Decorators ---

def requires_api_key(f):
    """Decorator to check for a valid API key in the request headers."""
    def decorated_function(*args, **kwargs):
        incoming_api_key = request.headers.get('X-API-KEY')
        if incoming_api_key != API_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def requires_jwt_auth(f):
    """Decorator to check for a valid JWT in the Authorization header."""
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            print("JWT missing or malformed.")
            return jsonify({"error": "JWT is missing or malformed"}), 401
        
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'], leeway=timedelta(seconds=10))
            user_email = payload.get('email')
            if not user_email:
                print("Invalid JWT payload: email missing.")
                return jsonify({"error": "Invalid JWT payload"}), 401
            # Add user_email from token payload into function arguments
            kwargs['user_email'] = user_email
            # print(f"JWT authenticated for user: {user_email}") # Less verbose
        except jwt.ExpiredSignatureError:
            print("JWT has expired.")
            return jsonify({"error": "JWT has expired"}), 401
        except jwt.InvalidTokenError as e:
            print(f"Invalid JWT: {e}")
            return jsonify({"error": "Invalid JWT"}), 401
        
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# --- API Endpoints ---

@app.route('/api/login', methods=['POST'])
@requires_api_key # Protect JWT generation with the static API key
def login():
    """Generates a JWT for a user. If the user does not exist, it creates a record (as non-trusted) and returns the JWT."""
    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            return jsonify({"status": "error", "message": "Database connection failed"}), 500
        
        data = request.json
        user_email = data.get("email")

        if not user_email:
            return jsonify({"status": "error", "message": "Email is required"}), 400

        # Determine if this email SHOULD be trusted based on environment variable
        should_be_trusted = user_email in TRUSTED_EMAILS_LIST

        # Fast path: user is cached and trust status hasn't changed — skip Redshift
        cached_user = _user_cache_get(user_email)
        if cached_user:
            user_id, db_is_trusted = cached_user
            if should_be_trusted == db_is_trusted:
                payload = {
                    'email': user_email,
                    'user_id': user_id,
                    'is_trusted': db_is_trusted,
                    'exp': datetime.now(timezone.utc) + timedelta(minutes=60)
                }
                access_token = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')
                print(f"JWT generated for {user_email} (cached), Trusted: {db_is_trusted}")
                release_db_connection(conn)
                conn = None
                return jsonify(token=access_token, is_trusted=db_is_trusted), 200

        with conn.cursor() as cur:
            # Check if user exists
            cur.execute("SELECT user_id, is_trusted FROM dim.dim_users WHERE user_email = %s;", (user_email,))
            user_record = cur.fetchone()
            user_id = None
            db_is_trusted = False # Status currently in DB

            if not user_record:
                # User doesn't exist, create them. Trust status based on env list.
                print(f"User {user_email} not found. Creating. Should be trusted: {should_be_trusted}")
                cur.execute("INSERT INTO dim.dim_users (user_email, is_trusted) VALUES (%s, %s);", (user_email, should_be_trusted))
                conn.commit()
                # Fetch the new user's ID and trust status
                cur.execute("SELECT user_id, is_trusted FROM dim.dim_users WHERE user_email = %s;", (user_email,))
                new_user_record = cur.fetchone()
                if new_user_record:
                    user_id, db_is_trusted = new_user_record
                    print(f"New user created with ID: {user_id}, DB Trusted: {db_is_trusted}")
                else:
                    raise Exception("Failed to retrieve user ID after insert.")
            else:
                # User exists, check if trust status needs updating
                user_id, db_is_trusted = user_record
                print(f"Existing user {user_email} found. DB Trusted: {db_is_trusted}. Should be trusted: {should_be_trusted}")
                # Sync DB trust status with environment list if different
                if should_be_trusted != db_is_trusted:
                    print(f"Updating user {user_email} trust status in DB to: {should_be_trusted}")
                    cur.execute("UPDATE dim.dim_users SET is_trusted = %s WHERE user_id = %s;", (should_be_trusted, user_id))
                    conn.commit()
                    db_is_trusted = should_be_trusted # Update local variable to reflect change

            _user_cache_set(user_email, user_id, db_is_trusted)

            # Generate JWT with the *final confirmed* trust status (db_is_trusted)
            payload = {
                'email': user_email,
                'user_id': user_id,
                'is_trusted': db_is_trusted,
                'exp': datetime.now(timezone.utc) + timedelta(minutes=60) # Token expiry time
            }
            access_token = jwt.encode(payload, JWT_SECRET_KEY, algorithm='HS256')
            print(f"JWT generated for {user_email}, Final DB Trusted: {db_is_trusted}")
            # Return token and the trust status confirmed/updated in DB
            return jsonify(token=access_token, is_trusted=db_is_trusted), 200
            
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error during login: {error}")
        if conn: conn.rollback()
        return jsonify({"status": "error", "message": f"Login failed: {str(error)}"}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/add_user', methods=['POST'])
@requires_api_key # Protect user creation with API Key
def add_user():
    """
    Adds a new user if they don't exist (as non-trusted).
    Used for registering guests who log in but aren't trusted. (Redshift Safe)
    """
    data = request.json
    user_email = data.get('email')

    if not user_email:
        return jsonify({"error": "Email is required"}), 400

    # Cache "already exists" responses for 6 hours — known users never disappear,
    # so repeated calls (e.g. every 5 min keep-alive) skip Redshift entirely.
    cache_key = f"add_user:{user_email}"
    cached = _cache_get(cache_key)
    if cached:
        return jsonify(cached[0]), cached[1]

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT 1 FROM dim.dim_users WHERE user_email = %s;", (user_email,))
        exists = cur.fetchone()

        if not exists:
            cur.execute("INSERT INTO dim.dim_users (user_email, is_trusted) VALUES (%s, %s);", (user_email, False))
            conn.commit()
            print(f"Registered guest user: {user_email}")
            return jsonify({"message": f"User {user_email} registered successfully."}), 201
        else:
             print(f"Guest user {user_email} already exists.")
             resp = {"message": f"User {user_email} already exists."}
             _cache_set(cache_key, resp, 200, ttl_seconds=21600)  # 6 hours
             return jsonify(resp), 200

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error while adding user: {error}")
        if conn: conn.rollback()
        return jsonify({"error": "An error occurred while adding the user."}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/add_trusted_user', methods=['POST'])
@requires_api_key # Secure this admin action
def add_trusted_user():
    """
    Adds or updates a user, explicitly setting the trusted flag. Requires API key. (Redshift Safe)
    This endpoint is for *manual* admin control over trust status, separate from the env list sync.
    """
    data = request.json
    user_email = data.get('email')
    is_trusted_flag = data.get('is_trusted', True) # Get desired status from payload

    if not user_email:
        return jsonify({"error": "Email is required"}), 400
    if not isinstance(is_trusted_flag, bool):
        return jsonify({"error": "'is_trusted' must be true or false"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT user_id FROM dim.dim_users WHERE user_email = %s;", (user_email,))
        user_record = cur.fetchone()

        if user_record:
            print(f"Updating trust status for existing user: {user_email} to {is_trusted_flag}")
            cur.execute("UPDATE dim.dim_users SET is_trusted = %s WHERE user_email = %s;", (is_trusted_flag, user_email))
        else:
            print(f"Adding new user with trust status: {user_email}, Trusted: {is_trusted_flag}")
            cur.execute("INSERT INTO dim.dim_users (user_email, is_trusted) VALUES (%s, %s);", (user_email, is_trusted_flag))

        conn.commit()
        print(f"Admin action: User {user_email} added/updated. Trusted status set to: {is_trusted_flag}.")
        return jsonify({"message": f"User {user_email} added/updated successfully. Trusted status set to: {is_trusted_flag}."}), 201
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error while adding/updating trusted user via admin endpoint: {error}")
        if conn: conn.rollback()
        return jsonify({"error": "An error occurred while managing the trusted user."}), 500
    finally:
        release_db_connection(conn)
        
# --- Stat Management Endpoints (add, delete, update) ---
def _social_media_pipeline(player_id, player_name, game_id, game_name,
                            game_installment, stats, is_live, credit_style, queue_platforms=None):
    """Run chart generation, GCS upload, and IFTTT trigger in a background thread.
    Uses its own DB connection so the main request can return immediately.

    queue_platforms: list of platform strings to enqueue e.g. ['twitter'], ['twitter', 'instagram'].
    GCS uploads always run regardless (backup). Platforms not in the list fire immediately via IFTTT
    (twitter) or are skipped (instagram — Lambda handles Instagram separately).
    """
    if queue_platforms is None:
        queue_platforms = []
    import traceback
    conn2 = None
    try:
        conn2 = get_db_connection()
        cur2 = conn2.cursor()

        batch_game_mode = next(
            (s.get('game_mode') for s in stats if s.get('game_mode') and s['game_mode'].strip()),
            None
        )

        cur2.execute("""
            SELECT COUNT(DISTINCT played_at) as games_played
            FROM fact.fact_game_stats
            WHERE player_id = %s AND game_id = %s;
        """, (player_id, game_id))
        games_played = cur2.fetchone()[0]

        print(f"📊 [bg] Generating chart for social media (Games played: {games_played})...")

        cur2.execute("""
            SELECT stat_type, AVG(stat_value) as avg_value
            FROM fact.fact_game_stats
            WHERE game_id = %s AND player_id = %s AND stat_type IS NOT NULL
            GROUP BY stat_type
            HAVING AVG(stat_value) > 0
            ORDER BY avg_value ASC
            LIMIT 3;
        """, (game_id, player_id))
        top_stats = [row[0] for row in cur2.fetchall()]

        if games_played == 1:
            stat_data = {}
            for i, stat_record in enumerate(stats[:3], 1):
                stat_type = stat_record.get('stat_type')
                if not stat_type:
                    continue
                stat_data[f'stat{i}'] = {
                    'label': stat_type,
                    'value': stat_record.get('stat_value', 0),
                    'prev_value': None
                }
                cur2.execute("""
                    SELECT stat_value FROM fact.fact_game_stats
                    WHERE player_id = %s AND game_id = %s AND stat_type = %s
                    ORDER BY played_at DESC LIMIT 2;
                """, (player_id, game_id, stat_type))
                prev_rows = cur2.fetchall()
                if len(prev_rows) > 1:
                    stat_data[f'stat{i}']['prev_value'] = prev_rows[1][0]

            image_buffer_twitter = generate_bar_chart(stat_data, player_name, game_name, game_installment, size='twitter', game_mode=batch_game_mode)
            image_buffer_instagram = generate_bar_chart(stat_data, player_name, game_name, game_installment, size='instagram', game_mode=batch_game_mode)
            chart_type = 'bar'
            stat_data_for_caption = stat_data
            _interactive_data = stat_data

        elif games_played > 1:
            stat_history = get_stat_history_from_db(cur2, player_id, game_id, top_stats, days_back=365)
            image_buffer_twitter = generate_line_chart(stat_history, player_name, game_name, game_installment, size='twitter', game_mode=batch_game_mode)
            image_buffer_instagram = generate_line_chart(stat_history, player_name, game_name, game_installment, size='instagram', game_mode=batch_game_mode)
            chart_type = 'line'
            stat_data_for_caption = {}
            for i in range(1, 4):
                key = f'stat{i}'
                if key in stat_history and stat_history[key]:
                    vals = stat_history[key].get('values', [])
                    stat_type_label = stat_history[key].get('label', '')
                    cur2.execute("""
                        SELECT stat_value FROM fact.fact_game_stats
                        WHERE player_id = %s AND game_id = %s AND stat_type = %s
                        ORDER BY played_at DESC LIMIT 2;
                    """, (player_id, game_id, stat_type_label))
                    prev_rows = cur2.fetchall()
                    stat_data_for_caption[key] = {
                        'label': stat_type_label,
                        'value': vals[-1] if vals else 0,
                        'prev_value': prev_rows[1][0] if len(prev_rows) > 1 else None
                    }
            _interactive_data = stat_history
        else:
            return

        interactive_url = None
        try:
            _html = generate_interactive_chart(
                chart_type, _interactive_data, player_name, game_name,
                game_installment=game_installment, game_mode=batch_game_mode
            )
            interactive_url = upload_interactive_chart_to_gcs(
                _html, player_name, game_name, game_installment
            )
        except Exception as _ie:
            print(f"⚠️  [bg] Interactive chart generation failed (non-fatal): {_ie}")

        twitter_public_url = upload_chart_to_gcs(image_buffer_twitter, player_name, game_name, chart_type, platform='twitter')
        instagram_url_week = upload_chart_to_gcs(image_buffer_instagram, player_name, game_name, chart_type, platform='instagram', storage_option='week')
        instagram_url_game = upload_chart_to_gcs(image_buffer_instagram, player_name, game_name, chart_type, platform='instagram', storage_option='game', game_installment=game_installment, game_mode=batch_game_mode)

        if twitter_public_url:
            caption = generate_post_caption(
                player_name, game_name, game_installment, stat_data_for_caption,
                games_played, platform='twitter', is_live=is_live,
                credit_style=credit_style, game_mode=batch_game_mode,
                interactive_url=interactive_url
            )
            if 'twitter' in queue_platforms:
                qid = enqueue_post(player_id, 'twitter', twitter_public_url, caption)
                print(f"📥 [bg] Twitter post queued (queue_id={qid})")
            else:
                success = trigger_ifttt_post(twitter_public_url, caption, 'twitter')
                print(f"{'✅' if success else '⚠️'} [bg] Twitter post {'triggered' if success else 'failed'}")
        else:
            print("⚠️ [bg] Failed to upload Twitter chart")

        instagram_url = instagram_url_game or instagram_url_week
        if instagram_url:
            instagram_caption = generate_post_caption(
                player_name, game_name, game_installment, stat_data_for_caption,
                games_played, platform='instagram', is_live=is_live,
                credit_style=credit_style, game_mode=batch_game_mode
            )
            if 'instagram' in queue_platforms:
                qid = enqueue_post(player_id, 'instagram', instagram_url, instagram_caption)
                print(f"📥 [bg] Instagram post queued (queue_id={qid})")

    except Exception as e:
        print(f"⚠️ [bg] Social media pipeline error (stats already saved): {e}")
        traceback.print_exc()
    finally:
        if conn2:
            release_db_connection(conn2)


# These now rely solely on the JWT for authentication and the DB for authorization (is_trusted check)

@app.route('/api/add_stats', methods=['POST'])
@requires_jwt_auth
def add_stats(user_email):
    """
    API endpoint to securely add game stats to the database.
    Requires a valid JWT for authentication.
    """
    data = request.json
    game_name = data.get('game_name')
    game_installment = data.get('game_installment')
    game_genre = data.get('game_genre')
    game_subgenre = data.get('game_subgenre')
    player_name = data.get('player_name')
    stats = data.get('stats')
    is_live = data.get('is_live', False)
    # queue_platforms: explicit list of platforms to enqueue e.g. ['twitter'], ['twitter','instagram']
    # Falls back to legacy queue_mode bool: True → ['twitter'] (Instagram never queued by default)
    if 'queue_platforms' in data:
        queue_platforms = data.get('queue_platforms', [])
    else:
        queue_platforms = ['twitter'] if data.get('queue_mode', False) else []
    credit_style = data.get('credit_style', 'shoutout')
    conn = None

    # This is a sample of the data that's expected
    # stats = [{
    #     "stat_type": "Eliminations",
    #     "stat_value": 15,
    #     "game_mode": "TDM",
    #     "game_level": 5,
    #     "win": 1,
    #     "ranked": 1,
    #     "pre_match_rank_value": "Gold",
    #     "post_match_rank_value": "Platinum"
    # },
    # {
    #     "stat_type": "Respawns",
    #     "stat_value": 10,
    #     "game_mode": "TDM",
    #     "game_level": 5,
    #     "win": 1,
    #     "ranked": 1,
    #     "pre_match_rank_value": "Gold",
    #     "post_match_rank_value": "Platinum"
    # }]

    if not all([game_name, player_name, stats]) or not isinstance(stats, list) or len(stats) == 0:
        return jsonify({"error": "Missing or invalid fields: game_name, player_name, and stats (must be a non-empty list)"}), 400

    # --- Batch-level validation (fast-fail before DB connection) ---
    if len(stats) > 10:
        return jsonify({"error": "Maximum 10 stat rows per submission."}), 400

    seen_stat_types = set()
    for s in stats:
        t = (s.get('stat_type') or '').strip().title()
        if not t:
            continue
        if t in seen_stat_types:
            return jsonify({"error": f"Duplicate stat type in submission: '{t}'"}), 400
        seen_stat_types.add(t)

    # --- Content safety checks ---
    err = _content_check(player_name, "Player name", _NAME_RE)
    if err: return jsonify(err[0]), err[1]

    err = _content_check(game_name, "Game name", _NAME_RE)
    if err: return jsonify(err[0]), err[1]

    if game_installment:
        err = _content_check(game_installment, "Game installment", _NAME_RE)
        if err: return jsonify(err[0]), err[1]

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get the user_id from the authenticated email
        cur.execute("SELECT user_id, is_trusted FROM dim.dim_users WHERE user_email = %s;", (user_email,))
        user_result = cur.fetchone()
        if not user_result: return jsonify({"error": "Authenticated user not found."}), 404
        user_id, is_trusted = user_result
        if not is_trusted: return jsonify({"error": "User not authorized"}), 403

        # --- Rate limiting (trusted users are exempt) ---
        if not is_trusted:
            if not _rate_limit_check(user_email, "add_stats", max_per_hour=50):
                return jsonify({"error": "Too many submissions. Please try again later."}), 429

        # --- Game Handling ---
        # Handle NULL game_installment properly
        if game_installment:
            cur.execute("SELECT game_id FROM dim.dim_games WHERE game_name = %s AND game_installment = %s;", (game_name, game_installment))
        else:
            cur.execute("SELECT game_id FROM dim.dim_games WHERE game_name = %s AND game_installment IS NULL;", (game_name,))

        game_record = cur.fetchone()
        game_id = None
        if not game_record:
            # Trusted users can create new games freely; public users must request
            if not is_trusted:
                return jsonify({
                    "error": "Game not found. Please select an existing game or submit a request to add it.",
                    "request_game": True
                }), 404
            print(f"Game '{game_name}' (Series: '{game_installment}') not found, creating.")
            cur.execute("""
                INSERT INTO dim.dim_games (game_name, game_installment, game_genre, game_subgenre, created_at, last_played_at)
                VALUES (%s, %s, %s, %s, GETDATE(), GETDATE());
            """, (game_name, game_installment, game_genre, game_subgenre))
            conn.commit()
            if game_installment:
                cur.execute("SELECT game_id FROM dim.dim_games WHERE game_name = %s AND game_installment = %s;", (game_name, game_installment))
            else:
                cur.execute("SELECT game_id FROM dim.dim_games WHERE game_name = %s AND game_installment IS NULL;", (game_name,))
            game_id_result = cur.fetchone()
            if not game_id_result: raise Exception("Failed to get game_id after insert.")
            game_id = game_id_result[0]
        else:
            game_id = game_record[0]
            cur.execute("UPDATE dim.dim_games SET last_played_at = GETDATE() WHERE game_id = %s;", (game_id,))

        # --- Player Handling ---
        cur.execute("SELECT player_id FROM dim.dim_players WHERE player_name = %s AND user_id = %s;", (player_name, user_id))
        player_record = cur.fetchone()
        player_id = None
        if not player_record:
            # Enforce player limit for non-trusted users
            if not is_trusted:
                cur.execute("SELECT COUNT(*) FROM dim.dim_players WHERE user_id = %s;", (user_id,))
                player_count = cur.fetchone()[0]
                if player_count >= MAX_FREE_PLAYERS:
                    return jsonify({
                        "error": f"Free accounts are limited to {MAX_FREE_PLAYERS} players. Upgrade to Premium for more."
                    }), 403
            # Rate limit new player creation
            if not is_trusted and not _rate_limit_check(user_email, "create_player", max_per_hour=5):
                return jsonify({"error": "Too many player creations. Try again later."}), 429
            print(f"Player '{player_name}' for user {user_id} not found, creating.")
            cur.execute("INSERT INTO dim.dim_players (player_name, user_id, created_at) VALUES (%s, %s, GETDATE());", (player_name, user_id))
            conn.commit()
            cur.execute("SELECT player_id FROM dim.dim_players WHERE player_name = %s AND user_id = %s;", (player_name, user_id))
            player_id_result = cur.fetchone()
            if not player_id_result: raise Exception("Failed to get player_id after insert.")
            player_id = player_id_result[0]
        else:
            player_id = player_record[0]

        # --- Duplicate session guard (2-minute window) ---
        # Prevents double-submits from double-clicks or form re-submissions.
        # Uses Python datetime so the comparison is DB-agnostic (works on both
        # Redshift and Supabase without changing GETDATE() / NOW() syntax).
        two_min_ago = datetime.now(timezone.utc) - timedelta(minutes=2)
        cur.execute("""
            SELECT 1 FROM fact.fact_game_stats
            WHERE player_id = %s AND game_id = %s AND played_at > %s
            LIMIT 1;
        """, (player_id, game_id, two_min_ago))
        if cur.fetchone():
            return jsonify({
                "error": "A session was already submitted in the last 2 minutes. "
                         "Check your recent stats before resubmitting."
            }), 409

        # --- Stat Insertion ---
        # Capture a single timestamp for the entire batch so all stats in this
        # session share the exact same played_at — prevents COUNT(DISTINCT played_at)
        # from counting one session as multiple games due to sub-second drift.
        cur.execute("SELECT GETDATE();")
        batch_timestamp = cur.fetchone()[0]

        successful_inserts = 0
        for stat_record in stats:
            if not stat_record.get('stat_type') or stat_record.get('stat_value') is None: continue

            # Normalize stat_type casing (e.g. "kills" → "Kills", "head shots" → "Head Shots")
            stat_record['stat_type'] = stat_record['stat_type'].strip().title()

            # Validate stat_type format and profanity
            err = _content_check(stat_record['stat_type'], "Stat type", _STAT_TYPE_RE)
            if err: return jsonify(err[0]), err[1]

            # Validate stat_value is numeric and in range
            val = stat_record.get('stat_value')
            if not isinstance(val, (int, float)) or val < 0 or val > 100_000:
                return jsonify({"error": f"stat_value out of range or invalid: {val}"}), 400

            # Validate boolean-like fields — must be 0, 1, or NULL (NULL = not applicable, e.g. zombies mode)
            for bool_field in ('win', 'ranked', 'overtime', 'solo_mode'):
                v = stat_record.get(bool_field)
                if v is not None and v not in (0, 1):
                    return jsonify({"error": f"'{bool_field}' must be 0, 1, or null — got: {v}"}), 400

            # Validate game_level (0–10,000, integers only)
            lvl = stat_record.get('game_level')
            if lvl is not None and (not isinstance(lvl, int) or lvl < 0 or lvl > 10_000):
                return jsonify({"error": f"game_level must be an integer between 0 and 10,000 — got: {lvl}"}), 400

            # Validate party_size against the frontend dropdown whitelist
            _VALID_PARTY_SIZES = {'1', '2', '3', '4', '5+'}
            ps = stat_record.get('party_size')
            if ps is not None and str(ps) not in _VALID_PARTY_SIZES:
                return jsonify({"error": f"Invalid party_size: '{ps}'. Must be one of: 1, 2, 3, 4, 5+"}), 400

            # Cross-field: ranked session requires a pre-match rank value
            if stat_record.get('ranked') == 1 and not stat_record.get('pre_match_rank_value'):
                return jsonify({"error": "ranked=1 requires pre_match_rank_value to be set"}), 400

            cur.execute("""
                INSERT INTO fact.fact_game_stats
                (game_id, player_id, stat_type, stat_value, game_mode, solo_mode, party_size,
                 game_level, win, ranked, pre_match_rank_value, post_match_rank_value,
                 overtime, difficulty, input_device, platform, first_session_of_day, was_streaming,
                 played_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                game_id, player_id, stat_record.get('stat_type'), stat_record.get('stat_value'),
                stat_record.get('game_mode'), stat_record.get('solo_mode'), stat_record.get('party_size'),
                stat_record.get('game_level'), stat_record.get('win'),
                stat_record.get('ranked'), stat_record.get('pre_match_rank_value'), stat_record.get('post_match_rank_value'),
                stat_record.get('overtime', 0), stat_record.get('difficulty'),
                stat_record.get('input_device', 'Controller'), stat_record.get('platform', 'PC'),
                stat_record.get('first_session_of_day', 0), stat_record.get('was_streaming', 0),
                batch_timestamp
            ))
            successful_inserts += 1
        if successful_inserts > 0:
            conn.commit()
            print(f"✅ {successful_inserts} stats inserted successfully")
            _cache_invalidate_obs()  # push fresh data to OBS on next poll

            # --- SOCIAL MEDIA INTEGRATION (background thread) ---
            # Capture all request-scoped data before releasing the DB connection.
            _bg_args = {
                'player_id': player_id,
                'player_name': player_name,
                'game_id': game_id,
                'game_name': game_name,
                'game_installment': game_installment,
                'stats': list(stats),
                'is_live': is_live,
                'credit_style': credit_style,
                'queue_platforms': queue_platforms,
            }
            threading.Thread(
                target=_social_media_pipeline,
                kwargs=_bg_args,
                daemon=True
            ).start()

            post_action = "queued" if queue_platforms else "posting"
            return jsonify({
                "message": f"Stats successfully added ({successful_inserts} records)!",
                "social_media": post_action
            }), 201

        else:
            return jsonify({"error": "No valid stats provided to insert."}), 400
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error: {error}"); conn.rollback()
        return jsonify({"error": f"An internal error occurred: {str(error)}"}), 500
    finally:
        release_db_connection(conn)


# --- Post Queue Endpoints ---

@app.route('/api/process_queue', methods=['POST'])
def process_queue():
    """
    Process the oldest pending post in post_queue and fire the IFTTT webhook.
    Protected by X-Cron-Secret header — called by the Render cron job.
    Also runs housekeeping: resets stale 'processing' rows and purges old sent rows.
    """
    incoming_secret = request.headers.get('X-Cron-Secret')
    if not CRON_SECRET or incoming_secret != CRON_SECRET:
        return jsonify({"error": "Unauthorized"}), 401

    results = {"processed": 0, "status": None, "queue_id": None, "purged": 0, "stale_reset": 0}

    # Housekeeping: reset any rows stuck in 'processing' for > 10 min
    try:
        stale = reset_stale_processing(minutes=10)
        results["stale_reset"] = stale
        if stale:
            print(f"♻️  Reset {stale} stale processing row(s) back to pending.")
    except Exception as e:
        print(f"⚠️  Stale reset error (non-fatal): {e}")

    # Housekeeping: purge sent rows older than 7 days
    try:
        purged = purge_old_sent(days=7)
        results["purged"] = purged
        if purged:
            print(f"🗑️  Purged {purged} old sent post(s) from queue.")
    except Exception as e:
        print(f"⚠️  Queue cleanup error (non-fatal): {e}")

    # Pick and atomically claim the oldest pending item
    try:
        item = get_oldest_pending()
    except Exception as e:
        return jsonify({"error": f"Queue read failed: {str(e)}"}), 500

    if not item:
        results["status"] = "empty"
        return jsonify(results), 200

    queue_id = item['queue_id']
    results["queue_id"] = queue_id

    try:
        success = trigger_ifttt_post(item['image_url'], item['caption'], item['platform'])
        new_status = 'sent' if success else 'failed'
        mark_status(queue_id, new_status)
        results["processed"] = 1
        results["status"] = new_status
        print(f"{'✅' if success else '❌'} Queue item {queue_id} ({item['platform']}): {new_status}")
        return jsonify(results), 200
    except Exception as e:
        try:
            mark_status(queue_id, 'failed')
        except Exception:
            pass
        return jsonify({"error": str(e), "queue_id": queue_id}), 500


@app.route('/api/queue_status', methods=['GET'])
@requires_jwt_auth
def queue_status(user_email):
    """Return pending/processing/sent/failed counts for the Streamlit UI."""
    try:
        counts = get_queue_counts()
        print(f"📊 Queue status requested by {user_email}: {counts}")
        return jsonify(counts), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/retry_failed', methods=['POST'])
@requires_jwt_auth
def retry_failed(user_email):
    """Reset all failed queue items back to pending."""
    try:
        count = reset_failed_to_pending()
        print(f"♻️  {user_email} reset {count} failed post(s) to pending.")
        return jsonify({"reset_count": count}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Player Endpoints ---

@app.route('/api/update_player/<int:player_id>', methods=['PUT'])
@requires_jwt_auth
def update_player(player_id, user_email):
    """Updates a player's name. User must be trusted and own the player."""
    data = request.json
    new_player_name = data.get('player_name')
    if not new_player_name:
        return jsonify({"error": "New player_name is required"}), 400
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Verify user is trusted AND owns this player
        cur.execute("""
            UPDATE dim.dim_players
            SET player_name = %s
            WHERE player_id = %s
            AND user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = %s AND is_trusted = TRUE);
        """, (new_player_name, player_id, user_email))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "Player not found or user not authorized."}), 404
        print(f"Player {player_id} updated to '{new_player_name}' by {user_email}")
        return jsonify({"message": "Player updated successfully."}), 200
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error updating player {player_id}: {error}"); conn.rollback()
        return jsonify({"error": f"An internal error occurred: {str(error)}"}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/delete_player/<int:player_id>', methods=['DELETE'])
@requires_jwt_auth
def delete_player(player_id, user_email):
    """Deletes a player and all their stats. User must be trusted and own the player."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get user_id and trust status
        cur.execute("SELECT user_id, is_trusted FROM dim.dim_users WHERE user_email = %s;", (user_email,))
        user_result = cur.fetchone()
        if not user_result or not user_result[1]:
             return jsonify({"error": "User not authorized to delete."}), 403
        user_id = user_result[0]

        # Verify player belongs to user
        cur.execute("SELECT 1 FROM dim.dim_players WHERE player_id = %s AND user_id = %s;", (player_id, user_id))
        player_exists = cur.fetchone()
        if not player_exists:
            return jsonify({"error": "Player not found or permission denied."}), 404

        # Delete associated stats first
        cur.execute("DELETE FROM fact.fact_game_stats WHERE player_id = %s;", (player_id,))
        print(f"Deleted {cur.rowcount} stats for player {player_id}")
        
        # Then delete the player
        cur.execute("DELETE FROM dim.dim_players WHERE player_id = %s AND user_id = %s;", (player_id, user_id))
        
        conn.commit()
        print(f"Player {player_id} deleted by user {user_email}")
        return jsonify({"message": "Player and all associated stats deleted."}), 200
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error deleting player {player_id}: {error}"); conn.rollback()
        return jsonify({"error": f"An internal error occurred: {str(error)}"}), 500
    finally:
        release_db_connection(conn)

# --- Game Endpoints ---

@app.route('/api/get_game_details/<int:game_id>', methods=['GET'])
@requires_jwt_auth
def get_game_details(game_id, user_email):
    """Gets details for a specific game if the user has stats for it."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Check if user has stats for this game (implies ownership)
        cur.execute("""
            SELECT 1 FROM fact.fact_game_stats
            WHERE game_id = %s
            AND player_id IN (SELECT player_id FROM dim.dim_players WHERE user_id = (
                SELECT user_id FROM dim.dim_users WHERE user_email = %s
            ));
        """, (game_id, user_email))
        has_stats = cur.fetchone()
        
        if not has_stats:
            return jsonify({"error": "Game not found or user has no stats for it."}), 404
            
        # User has stats, so fetch game details
        cur.execute("SELECT game_name, game_installment, game_genre, game_subgenre FROM dim.dim_games WHERE game_id = %s;", (game_id,))
        game = cur.fetchone()
        if not game:
            return jsonify({"error": "Game not found."}), 404
        
        game_details = {"game_name": game[0], "game_installment": game[1], "game_genre": game[2], "game_subgenre": game[3]}
        return jsonify(game_details), 200
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error fetching game details for {game_id}: {error}")
        return jsonify({"error": f"An internal error occurred: {str(error)}"}), 500
    finally:
        release_db_connection(conn)


@app.route('/api/update_game/<int:game_id>', methods=['PUT'])
@requires_jwt_auth
def update_game(game_id, user_email):
    """Updates a game's details. User must be trusted and have stats for the game."""
    data = request.json
    game_name = data.get('game_name')
    game_installment = data.get('game_installment')
    game_genre = data.get('game_genre')
    game_subgenre = data.get('game_subgenre')
    
    if not game_name:
        return jsonify({"error": "New game_name is required"}), 400
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Verify user is trusted
        cur.execute("SELECT user_id, is_trusted FROM dim.dim_users WHERE user_email = %s;", (user_email,))
        user_result = cur.fetchone()
        if not user_result or not user_result[1]:
             return jsonify({"error": "User not authorized to update."}), 403
        user_id = user_result[0]
        
        # Verify user has stats for this game (implied ownership)
        cur.execute("""
            SELECT 1 FROM fact.fact_game_stats
            WHERE game_id = %s AND player_id IN (SELECT player_id FROM dim.dim_players WHERE user_id = %s);
        """, (game_id, user_id))
        has_stats = cur.fetchone()
        
        if not has_stats:
            return jsonify({"error": "Game not found or user has no stats for it."}), 404

        # User is trusted and has stats, proceed with update
        cur.execute("""
            UPDATE dim.dim_games
            SET game_name = %s, game_installment = %s, game_genre = %s, game_subgenre = %s
            WHERE game_id = %s;
        """, (game_name, game_installment, game_genre, game_subgenre, game_id))
        conn.commit()
        
        print(f"Game {game_id} updated to '{game_name}' by {user_email}")
        return jsonify({"message": "Game updated successfully."}), 200
    except (Exception, psycopg2.DatabaseError) as error:
        # Handle potential unique constraint violation on game_name
        if "unique constraint" in str(error).lower():
            print(f"Error updating game {game_id}: Name '{game_name}' already exists.")
            return jsonify({"error": f"Game name '{game_name}' already exists."}), 409 # 409 Conflict
        print(f"Error updating game {game_id}: {error}"); conn.rollback()
        return jsonify({"error": f"An internal error occurred: {str(error)}"}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/delete_game/<int:game_id>', methods=['DELETE'])
@requires_jwt_auth
def delete_game(game_id, user_email):
    """Deletes a game. User must be trusted. Game must have NO associated stats."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Verify user is trusted
        cur.execute("SELECT user_id, is_trusted FROM dim.dim_users WHERE user_email = %s;", (user_email,))
        user_result = cur.fetchone()
        if not user_result or not user_result[1]:
             return jsonify({"error": "User not authorized to delete."}), 403
        user_id = user_result[0]

        # CRITICAL: Check if any stats still reference this game
        cur.execute("SELECT 1 FROM fact.fact_game_stats WHERE game_id = %s LIMIT 1;", (game_id,))
        stats_exist = cur.fetchone()
        
        if stats_exist:
            print(f"Attempt to delete game {game_id} failed: Stats still exist.")
            return jsonify({"error": "Cannot delete game. All associated stats must be deleted first."}), 409 # 409 Conflict
            
        # No stats exist, proceed with deletion
        # Optional: Check if user *used* to have stats for this game?
        # For simplicity, we allow any trusted user to delete an orphaned game.
        cur.execute("DELETE FROM dim.dim_games WHERE game_id = %s;", (game_id,))
        conn.commit()
        
        if cur.rowcount == 0:
            return jsonify({"error": "Game not found."}), 404
            
        print(f"Game {game_id} deleted by user {user_email}")
        return jsonify({"message": "Game successfully deleted."}), 200
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error deleting game {game_id}: {error}"); conn.rollback()
        return jsonify({"error": f"An internal error occurred: {str(error)}"}), 500
    finally:
        release_db_connection(conn)


# --- Delete Stats Endpoints ---

@app.route('/api/delete_stats/<int:stat_id>', methods=['DELETE'])
@requires_jwt_auth
def delete_stats(stat_id, user_email):
    """
    Deletes a stat entry. If it's the last stat for that game *for that user*,
    returns a flag to prompt front-end.
    """
    conn = None
    game_id_to_check = None
    user_id = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get user_id and trust status
        cur.execute("SELECT user_id, is_trusted FROM dim.dim_users WHERE user_email = %s;", (user_email,))
        user_result = cur.fetchone()
        if not user_result or not user_result[1]:
             return jsonify({"error": "User not authorized to delete stats"}), 403
        user_id = user_result[0]

        # Get game_id *before* deleting, and verify ownership
        cur.execute("""
            SELECT gs.game_id
            FROM fact.fact_game_stats gs
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            WHERE gs.stat_id = %s AND p.user_id = %s;
        """, (stat_id, user_id))
        stat_info = cur.fetchone()
        
        if not stat_info:
            return jsonify({"message": f"Stat with ID {stat_id} not found or permission denied."}), 404
        game_id_to_check = stat_info[0]

        # Perform the delete
        cur.execute("DELETE FROM fact.fact_game_stats WHERE stat_id = %s;", (stat_id,))
        print(f"Stat entry {stat_id} deleted by user {user_email}")
        
        # Check if any *other* stats exist for this game *for this user*
        cur.execute("""
            SELECT 1 FROM fact.fact_game_stats gs
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            WHERE gs.game_id = %s AND p.user_id = %s
            LIMIT 1;
        """, (game_id_to_check, user_id))
        other_stats_exist = cur.fetchone()
        
        conn.commit()
        
        response_data = {"message": "Entry successfully deleted."}
        if not other_stats_exist:
            # This was the last stat for this game *for this user*
            # Check if *any* stats exist for this game at all
            cur.execute("SELECT 1 FROM fact.fact_game_stats WHERE game_id = %s LIMIT 1;", (game_id_to_check,))
            any_stats_exist = cur.fetchone()
            if not any_stats_exist:
                print(f"Last stat for game {game_id_to_check} was deleted by {user_email}.")
                response_data["last_stat_deleted"] = True
                response_data["game_id"] = game_id_to_check
        
        return jsonify(response_data), 200
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error while deleting stats: {error}"); conn.rollback()
        return jsonify({"error": f"An error occurred while deleting the entry: {str(error)}"}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/get_recent_stats', methods=['GET'])
@requires_jwt_auth
def get_recent_stats(user_email):
    """Returns the 50 most recent stat entries with z-score anomaly detection."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # hist CTE computes mean/std over ALL of the user's data per (game, stat_type)
        # so z-scores are relative to full history, not just the 50 returned rows.
        cur.execute("""
            WITH hist AS (
                SELECT
                    gs.game_id,
                    gs.stat_type,
                    AVG(gs.stat_value::float)    AS hist_mean,
                    STDDEV_SAMP(gs.stat_value::float) AS hist_std,
                    COUNT(*)                     AS hist_count
                FROM fact.fact_game_stats gs
                JOIN dim.dim_players p ON gs.player_id = p.player_id
                WHERE p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = %s)
                GROUP BY gs.game_id, gs.stat_type
            )
            SELECT
                gs.stat_id,
                p.player_name,
                g.game_name,
                g.game_installment,
                g.game_id,
                gs.stat_type,
                gs.stat_value,
                gs.game_mode,
                gs.game_level,
                gs.win,
                gs.ranked,
                gs.pre_match_rank_value,
                gs.post_match_rank_value,
                gs.played_at,
                h.hist_mean,
                h.hist_std,
                h.hist_count
            FROM fact.fact_game_stats gs
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            JOIN dim.dim_games g ON gs.game_id = g.game_id
            LEFT JOIN hist h ON gs.game_id = h.game_id AND gs.stat_type = h.stat_type
            WHERE p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = %s)
            ORDER BY gs.played_at DESC
            LIMIT 50;
        """, (user_email, user_email))
        rows = cur.fetchall()

        def _outlier_fields(value, mean, std, count):
            if count is None or count < 5 or std is None or std == 0:
                return {"is_outlier": False, "z_score": None, "percentile": None}
            z = (float(value) - float(mean)) / float(std)
            return {
                "is_outlier": abs(z) > 2.0,
                "z_score": round(z, 2),
                "percentile": int(scipy_stats.norm.cdf(z) * 100),
            }

        stats = []
        for row in rows:
            entry = {
                "stat_id": row[0],
                "player_name": row[1],
                "game_name": row[2],
                "game_installment": row[3],
                "game_id": row[4],
                "stat_type": row[5],
                "stat_value": row[6],
                "game_mode": row[7],
                "game_level": row[8],
                "win": row[9],
                "ranked": row[10],
                "pre_match_rank_value": row[11],
                "post_match_rank_value": row[12],
                "played_at": row[13].isoformat() if row[13] else None,
            }
            entry.update(_outlier_fields(row[6], row[14], row[15], row[16]))
            stats.append(entry)

        return jsonify({"stats": stats}), 200
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error fetching recent stats for {user_email}: {error}")
        return jsonify({"error": "An error occurred while fetching stats."}), 500
    finally:
        release_db_connection(conn)


@app.route('/api/update_stats/<int:stat_id>', methods=['PUT'])
@requires_jwt_auth
def update_stats(stat_id, user_email):
    """Updates an individual stat entry. User must be trusted and own the stat."""
    data = request.json or {}
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Verify caller is trusted and owns this stat
        cur.execute("""
            SELECT gs.stat_id
            FROM fact.fact_game_stats gs
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            JOIN dim.dim_users u ON p.user_id = u.user_id
            WHERE gs.stat_id = %s AND u.user_email = %s AND u.is_trusted = TRUE;
        """, (stat_id, user_email))
        if not cur.fetchone():
            return jsonify({"error": "Stat not found or not authorized."}), 404

        cur.execute("""
            UPDATE fact.fact_game_stats SET
                stat_type              = COALESCE(%s, stat_type),
                stat_value             = COALESCE(%s, stat_value),
                game_mode              = COALESCE(%s, game_mode),
                game_level             = %s,
                win                    = %s,
                ranked                 = COALESCE(%s, ranked),
                pre_match_rank_value   = %s,
                post_match_rank_value  = %s
            WHERE stat_id = %s;
        """, (
            data.get('stat_type'),
            data.get('stat_value'),
            data.get('game_mode'),
            data.get('game_level'),
            data.get('win'),
            data.get('ranked'),
            data.get('pre_match_rank_value'),
            data.get('post_match_rank_value'),
            stat_id,
        ))
        conn.commit()
        print(f"Stat {stat_id} updated by {user_email}")
        return jsonify({"message": "Stat updated successfully."}), 200
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error updating stat {stat_id}: {error}"); conn.rollback()
        return jsonify({"error": f"An error occurred: {str(error)}"}), 500
    finally:
        release_db_connection(conn)


# --- Read Endpoints ---

@app.route('/api/get_players', methods=['GET'])
@requires_jwt_auth
def get_players(user_email):
    """Gets players (id, name) associated ONLY with the authenticated user."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT player_id, player_name FROM dim.dim_players
            WHERE user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = %s)
            ORDER BY player_name;
        """, (user_email,))
        # Return list of dicts
        players = [{"player_id": row[0], "player_name": row[1]} for row in cur.fetchall()]
        return jsonify({"players": players}), 200
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error while fetching players for user {user_email}: {error}")
        return jsonify({"error": "An error occurred while fetching players."}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/get_games', methods=['GET'])
@requires_jwt_auth
def get_games(user_email):
    """Gets all games the authenticated user has stats for. Returns [ {id, name}, ... ]."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT g.game_id, g.game_name, g.game_installment
            FROM dim.dim_games g
            JOIN fact.fact_game_stats gs ON g.game_id = gs.game_id
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            WHERE p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = %s)
            ORDER BY g.game_name, g.game_installment;
        """, (user_email,))
        games = [
            {"game_id": row[0], "game_name": row[1], "game_installment": row[2]}
            for row in cur.fetchall()
        ]
        return jsonify({"games": games}), 200
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error while fetching games for user {user_email}: {error}")
        return jsonify({"error": "An error occurred while fetching games."}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/get_game_ranks/<int:game_id>', methods=['GET']) # Changed to game_id
@requires_jwt_auth
def get_game_ranks_by_id(game_id, user_email): # Renamed function
    """Gets ranks for a specific game, scoped to the user."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT rank_value
            FROM (
                SELECT pre_match_rank_value AS rank_value FROM fact.fact_game_stats gs
                JOIN dim.dim_players p ON gs.player_id = p.player_id
                WHERE gs.game_id = %s AND gs.ranked = 1 AND gs.pre_match_rank_value IS NOT NULL
                AND p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = %s)
                UNION
                SELECT post_match_rank_value AS rank_value FROM fact.fact_game_stats gs
                JOIN dim.dim_players p ON gs.player_id = p.player_id
                WHERE gs.game_id = %s AND gs.ranked = 1 AND gs.post_match_rank_value IS NOT NULL
                AND p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = %s)
            ) AS combined_ranks
            WHERE rank_value IS NOT NULL AND rank_value != ''
            ORDER BY rank_value;
        """, (game_id, user_email, game_id, user_email))
        ranks = [row[0] for row in cur.fetchall()]
        return jsonify({"ranks": ranks}), 200
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error while fetching ranks for game {game_id}: {error}")
        return jsonify({"error": "An error occurred while fetching ranks."}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/get_game_modes/<int:game_id>', methods=['GET'])
@requires_jwt_auth
def get_game_modes(game_id, user_email):
    """Gets all unique game modes for a specific game, scoped to the user."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT game_mode
            FROM fact.fact_game_stats gs
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            WHERE gs.game_id = %s AND p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = %s)
            AND gs.game_mode IS NOT NULL AND gs.game_mode != ''
            ORDER BY game_mode;
        """, (game_id, user_email))
        modes = [row[0] for row in cur.fetchall()]
        return jsonify({"game_modes": modes}), 200
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error fetching game modes for game {game_id}: {error}")
        return jsonify({"error": "An error occurred fetching game modes."}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/get_game_stat_types/<int:game_id>', methods=['GET'])
@requires_jwt_auth
def get_game_stat_types(game_id, user_email):
    """Gets all unique stat types for a specific game, scoped to the user."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT gs.stat_type
            FROM fact.fact_game_stats gs
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            WHERE gs.game_id = %s AND p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = %s)
            AND gs.stat_type IS NOT NULL AND gs.stat_type != ''
            ORDER BY stat_type;
        """, (game_id, user_email))
        stat_types = [row[0] for row in cur.fetchall()]
        return jsonify({"stat_types": stat_types}), 200
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error fetching stat types for game {game_id}: {error}")
        return jsonify({"error": "An error occurred fetching stat types."}), 500
    finally:
        release_db_connection(conn)


@app.route('/api/get_game_context/<int:game_id>', methods=['GET'])
@requires_jwt_auth
def get_game_context(game_id, user_email):
    """Returns ranks, modes, and stat types for a game in a single DB connection.
    Replaces three separate API calls from the web/mobile client."""
    cache_key = f"context_{user_email}_{game_id}"
    cached = _cache_get(cache_key)
    if cached:
        return jsonify(cached[0]), cached[1]

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT DISTINCT rank_value FROM (
                SELECT pre_match_rank_value AS rank_value FROM fact.fact_game_stats gs
                JOIN dim.dim_players p ON gs.player_id = p.player_id
                WHERE gs.game_id = %s AND gs.ranked = 1 AND gs.pre_match_rank_value IS NOT NULL
                AND p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = %s)
                UNION
                SELECT post_match_rank_value AS rank_value FROM fact.fact_game_stats gs
                JOIN dim.dim_players p ON gs.player_id = p.player_id
                WHERE gs.game_id = %s AND gs.ranked = 1 AND gs.post_match_rank_value IS NOT NULL
                AND p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = %s)
            ) AS combined_ranks
            WHERE rank_value IS NOT NULL AND rank_value != ''
            ORDER BY rank_value;
        """, (game_id, user_email, game_id, user_email))
        ranks = [row[0] for row in cur.fetchall()]

        cur.execute("""
            SELECT DISTINCT game_mode FROM fact.fact_game_stats gs
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            WHERE gs.game_id = %s AND p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = %s)
            AND gs.game_mode IS NOT NULL AND gs.game_mode != ''
            ORDER BY game_mode;
        """, (game_id, user_email))
        modes = [row[0] for row in cur.fetchall()]

        cur.execute("""
            SELECT DISTINCT gs.stat_type FROM fact.fact_game_stats gs
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            WHERE gs.game_id = %s AND p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = %s)
            AND gs.stat_type IS NOT NULL AND gs.stat_type != ''
            ORDER BY stat_type;
        """, (game_id, user_email))
        stat_types = [row[0] for row in cur.fetchall()]

        result = {"ranks": ranks, "modes": modes, "stat_types": stat_types}
        _cache_set(cache_key, result, 200, 600)  # Cache for 10 minutes
        return jsonify(result), 200
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error fetching game context for game {game_id}: {error}")
        return jsonify({"error": "An error occurred fetching game context."}), 500
    finally:
        release_db_connection(conn)


@app.route('/api/get_game_franchises', methods=['GET'])
@requires_jwt_auth
def get_game_franchises(user_email):
    """Gets all unique game names (franchises) the authenticated user has stats for."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT g.game_name
            FROM dim.dim_games g
            JOIN fact.fact_game_stats gs ON g.game_id = gs.game_id
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            WHERE p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = %s)
            AND g.game_name IS NOT NULL
            ORDER BY g.game_name;
        """, (user_email,))
        franchises = [row[0] for row in cur.fetchall()]
        return jsonify({"game_franchises": franchises}), 200
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error: {error}")
        return jsonify({"error": "An error occurred."}), 500
    finally:
        release_db_connection(conn)

@app.route('/api/get_game_installments/<path:franchise_name>', methods=['GET'])
@requires_jwt_auth
def get_game_installments(franchise_name, user_email):
    """Gets games (id, installment) for a specific franchise, scoped to the user."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT DISTINCT g.game_id, g.game_installment
            FROM dim.dim_games g
            JOIN fact.fact_game_stats gs ON g.game_id = gs.game_id
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            WHERE p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = %s)
            AND g.game_name = %s
            ORDER BY g.game_installment;
        """, (user_email, franchise_name))
        
        installments = [{"game_id": row[0], "installment_name": row[1] if row[1] is not None else "(Main Game)"} for row in cur.fetchall()]
        return jsonify({"game_installments": installments}), 200
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error: {error}")
        return jsonify({"error": "An error occurred."}), 500
    finally:
        release_db_connection(conn)


# --- ENDPOINT for Streamlit to set state ---       
@app.route('/api/set_live_state', methods=['POST'])
@requires_jwt_auth # Secured by admin's JWT
def set_live_state(user_email):
    """
    Called by Streamlit to update the "current" game/player
    for the OBS dashboard to read.
    """
    data = request.json
    player_id = data.get('player_id')
    game_id = data.get('game_id')

    if not player_id or not game_id:
        return jsonify({"error": "player_id and game_id are required"}), 400
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Verify user is trusted (extra check)
        cur.execute("SELECT 1 FROM dim.dim_users WHERE user_email = %s AND is_trusted = TRUE;", (user_email,))
        if not cur.fetchone():
            return jsonify({"error": "User not authorized"}), 403
            
        # Update the single row in the state table
        cur.execute("""
            UPDATE dim.dim_dashboard_state
            SET current_player_id = %s,
                current_game_id = %s,
                updated_at = GETDATE()
            WHERE state_id = 1;
        """, (player_id, game_id))
        conn.commit()
        
        return jsonify({"message": "Live state updated"}), 200
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error setting live state: {error}"); conn.rollback()
        return jsonify({"error": f"An internal error occurred: {str(error)}"}), 500
    finally:
        release_db_connection(conn)

# --- OBS Active State Endpoints ---
@app.route('/api/obs_status', methods=['GET'])
@requires_jwt_auth
def get_obs_status(user_email):
    """Returns the current OBS active flag."""
    return jsonify({"obs_active": obs_active}), 200

@app.route('/api/set_obs_active', methods=['POST'])
@requires_jwt_auth
def set_obs_active(user_email):
    """
    Called by Streamlit to activate/deactivate the OBS overlay and ticker.
    When obs_active=False, get_live_dashboard and get_stat_ticker skip Redshift
    and return an idle response, eliminating background queries.
    """
    global obs_active
    data = request.json
    obs_active = bool(data.get('active', False))
    status = "active" if obs_active else "sleeping"
    print(f"🎬 OBS overlay {status}")
    return jsonify({"obs_active": obs_active}), 200

# --- DYNAMIC OBS DASHBOARD ENDPOINT ---
@app.route('/api/get_live_dashboard', methods=['GET'])
def get_live_dashboard():
    """
    A public-but-secret endpoint for OBS.
    Fetches stats for the *currently set* player/game for the day.
    Falls back to most recent day's averages.
    
    Special logic:
    - If game has win tracking (win column has non-NULL values), returns:
      * Wins (SUM of win=1 by distinct played_at)
      * Top 2 relevant stats (highest non-zero AVG, ascending order)
    - Otherwise returns top 3 relevant stats
    
    Example URL:
    .../api/get_live_dashboard?key=OBS_SECRET_KEY&tz=America/New_York
    """
    # 1. Check for the secret key
    key = request.args.get('key')
    if key != OBS_SECRET_KEY:
        return jsonify({"error": "Unauthorized. Invalid or missing key."}), 401

    # 2. Skip Redshift entirely when OBS is not active
    if not obs_active:
        return jsonify({"obs_active": False, "message": "OBS overlay sleeping — activate via Streamlit to load stats."}), 200

    # 3. Get timezone
    timezone_str = request.args.get('tz', 'UTC')

    # --- 30-second response cache (avoids a DB round-trip on every OBS poll) ---
    _dash_cache_key = f"dash_{key}_{timezone_str}"
    _cached = _cache_get(_dash_cache_key)
    if _cached:
        print("📦 get_live_dashboard: serving cached response")
        return jsonify(_cached[0]), _cached[1]
    
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 3. Get the current state
        cur.execute("SELECT current_player_id, current_game_id FROM dim.dim_dashboard_state WHERE state_id = 1;")
        state = cur.fetchone()
        if not state or not state[0] or not state[1]:
            return jsonify({"error": "No live game/player selected in the Streamlit app."}), 404
        
        player_id, game_id = state
        
        # 4. Get "today" in the user's timezone
        try:
            cur.execute("SELECT CAST(CONVERT_TIMEZONE(%s, GETDATE()) AS DATE)", (timezone_str,))
            today_date = cur.fetchone()[0]
        except (Exception, psycopg2.DatabaseError) as tz_error:
            print(f"Timezone conversion error: {tz_error}. Defaulting to UTC.")
            cur.execute("SELECT CAST(GETDATE() AS DATE)")
            today_date = cur.fetchone()[0]
            timezone_str = 'UTC'

        # 5. Check if game has win tracking (any non-NULL win values)
        cur.execute("""
            SELECT COUNT(*) 
            FROM fact.fact_game_stats
            WHERE game_id = %s AND win IS NOT NULL
            LIMIT 1;
        """, (game_id,))
        has_win_tracking = cur.fetchone()[0] > 0

        # 6. Determine top stats based on win tracking
        top_stats = []
        include_wins = False
        
        if has_win_tracking:
            # Get top 2 relevant stats (player_id scopes the scan)
            cur.execute("""
                SELECT stat_type, AVG(stat_value) as avg_value
                FROM fact.fact_game_stats
                WHERE game_id = %s
                  AND player_id = %s
                  AND stat_type IS NOT NULL
                  AND stat_type != ''
                  AND stat_value > 0
                GROUP BY stat_type
                HAVING AVG(stat_value) > 0
                ORDER BY avg_value ASC
                LIMIT 2;
            """, (game_id, player_id))
            top_stats = [row[0] for row in cur.fetchall()]
            include_wins = True
            print(f"Win tracking enabled. Top 2 relevant stats: {top_stats}")
        else:
            # Get top 3 relevant stats (player_id scopes the scan)
            cur.execute("""
                SELECT stat_type, AVG(stat_value) as avg_value
                FROM fact.fact_game_stats
                WHERE game_id = %s
                  AND player_id = %s
                  AND stat_type IS NOT NULL
                  AND stat_type != ''
                  AND stat_value > 0
                GROUP BY stat_type
                HAVING AVG(stat_value) > 0
                ORDER BY avg_value ASC
                LIMIT 3;
            """, (game_id, player_id))
            top_stats = [row[0] for row in cur.fetchall()]
            print(f"No win tracking. Top 3 relevant stats: {top_stats}")
        
        # Handle brand new games with no stats yet
        if not top_stats and not include_wins:
            print(f"No stats found for game {game_id}. Returning placeholder values.")
            return jsonify({
                "stat1": {"label": "STAT 1", "value": 0},
                "stat2": {"label": "STAT 2", "value": 0},
                "stat3": {"label": "STAT 3", "value": 0},
                "time_period": "NEW GAME"
            }), 200

        # 7. Check for stats *today*
        cur.execute("""
            SELECT 1 FROM fact.fact_game_stats
            WHERE player_id = %s
              AND game_id = %s
              AND CAST(CONVERT_TIMEZONE(%s, played_at) AS DATE) = %s
            LIMIT 1;
        """, (player_id, game_id, timezone_str, today_date))
        stats_today_exist = cur.fetchone()

        results = {}
        query_date = today_date
        time_period = "TODAY"  # Changed from label_suffix
        
        # 8. If no stats today, find most recent day
        if not stats_today_exist:
            cur.execute("""
                SELECT MAX(CAST(CONVERT_TIMEZONE(%s, played_at) AS DATE))
                FROM fact.fact_game_stats
                WHERE player_id = %s
                  AND game_id = %s
                  AND CAST(CONVERT_TIMEZONE(%s, played_at) AS DATE) < %s;
            """, (timezone_str, player_id, game_id, timezone_str, today_date))
            most_recent_day = cur.fetchone()
            if most_recent_day and most_recent_day[0]:
                query_date = most_recent_day[0]
                time_period = "PAST"  # Changed from label_suffix
            else:
                # No stats today OR any day before. Return defaults.
                stat_index = 1
                if include_wins:
                    results['stat1'] = {"label": "WINS", "value": "---"}
                    stat_index = 2
                for i, stat_type in enumerate(top_stats, stat_index):
                    abbrev = abbreviate_stat(stat_type)
                    results[f'stat{i}'] = {"label": f"{abbrev}", "value": "---"}
                results['time_period'] = "N/A"  # Add time period to response
                return jsonify(results), 200

        # 9. Helper function to abbreviate stat labels
        def abbreviate_stat(stat_name):
            """Abbreviate stat name to 4 letters + 's'"""
            if not stat_name:
                return "XXXX"
            # Remove common words and get first 4 chars
            clean = stat_name.replace("Total", "").replace("Average", "").strip()
            if len(clean) > 8:
                abbrev = clean[:4].upper() + "S"
            else:
                abbrev = clean.upper()
            return f"{abbrev}"

        # 10. Build & Execute queries for the determined date
        stat_index = 1
        
        # Handle WINS if win tracking exists
        if include_wins:
            win_count = 0
            if stats_today_exist:
                # Today's wins: Count distinct played_at where win=1
                cur.execute("""
                    SELECT COUNT(DISTINCT played_at)
                    FROM fact.fact_game_stats
                    WHERE player_id = %s 
                      AND game_id = %s 
                      AND win = 1
                      AND CAST(CONVERT_TIMEZONE(%s, played_at) AS DATE) = %s;
                """, (player_id, game_id, timezone_str, query_date))
            else:
                # Last day average: AVG of wins per day
                cur.execute("""
                    SELECT AVG(daily_wins)
                    FROM (
                        SELECT CAST(CONVERT_TIMEZONE(%s, played_at) AS DATE) as play_date,
                               COUNT(DISTINCT played_at) as daily_wins
                        FROM fact.fact_game_stats
                        WHERE player_id = %s 
                          AND game_id = %s 
                          AND win = 1
                          AND CAST(CONVERT_TIMEZONE(%s, played_at) AS DATE) = %s
                        GROUP BY CAST(CONVERT_TIMEZONE(%s, played_at) AS DATE)
                    ) daily_win_counts;
                """, (timezone_str, player_id, game_id, timezone_str, query_date, timezone_str))
            
            result = cur.fetchone()
            if result and result[0] is not None:
                win_count = int(round(float(result[0])))
            
            results['stat1'] = {"label": "WINS", "value": win_count}
            stat_index = 2

        # Handle other stats — one batched query instead of one query per stat
        if top_stats:
            placeholders = ','.join(['%s'] * len(top_stats))
            agg_func = 'SUM' if stats_today_exist else 'AVG'
            cur.execute(f"""
                SELECT stat_type, {agg_func}(stat_value)
                FROM fact.fact_game_stats
                WHERE player_id = %s AND game_id = %s
                  AND stat_type IN ({placeholders})
                  AND CAST(CONVERT_TIMEZONE(%s, played_at) AS DATE) = %s
                GROUP BY stat_type;
            """, (player_id, game_id, *top_stats, timezone_str, query_date))
            stat_results = {row[0]: row[1] for row in cur.fetchall()}

            for i, stat_type in enumerate(top_stats, stat_index):
                abbrev = abbreviate_stat(stat_type)
                raw = stat_results.get(stat_type)
                if raw is not None:
                    value = int(raw) if stats_today_exist else round(float(raw))
                else:
                    value = 0
                results[f'stat{i}'] = {"label": f"{abbrev}", "value": value}

        # Add time_period to response
        results['time_period'] = time_period
        _cache_set(_dash_cache_key, results, 200, ttl_seconds=600)  # 10 minutes — cache invalidated immediately on stat submit
        return jsonify(results), 200
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error fetching live dashboard stats: {error}")
        if conn: conn.rollback()
        return jsonify({"error": f"An error occurred fetching live stats: {str(error)}"}), 500
    finally:
        release_db_connection(conn)
        
@app.route('/dashboard')
def serve_dashboard():
    """
    Serve the OBS dashboard HTML page
    
    Example URL:
    .../dashboard?key=OBS_SECRET_KEY&tz=America/New_York
    """
    return send_file('index.html')

# --- Game Stat Ticker --- 
@app.route('/api/get_stat_ticker', methods=['GET'])
def get_stat_ticker():
    """
    Returns educational stat facts for the ticker based on games played.
    Tiers:
    - 1-2 games: Basic facts (best performance, high scores)
    - 3-30 games: + Descriptive stats (mean, median, mode, min, max, range)
    - 30+ games: + Advanced stats (percentile, std dev, variance)
    """
    key = request.args.get('key')
    if key != OBS_SECRET_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    # Skip Redshift entirely when OBS is not active
    if not obs_active:
        return jsonify({"obs_active": False, "message": "OBS ticker sleeping — activate via Streamlit to load stats."}), 200

    timezone_str = request.args.get('tz', 'UTC')

    # --- 5-minute response cache (ticker facts change only when new stats arrive) ---
    _ticker_cache_key = f"ticker_{key}_{timezone_str}"
    _cached = _cache_get(_ticker_cache_key)
    if _cached:
        print("📦 get_stat_ticker: serving cached response")
        return jsonify(_cached[0]), _cached[1]

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get current player/game
        cur.execute("SELECT current_player_id, current_game_id FROM dim.dim_dashboard_state WHERE state_id = 1;")
        state = cur.fetchone()
        if not state or not state[0] or not state[1]:
            return jsonify({"error": "No live game/player selected"}), 404
        
        player_id, game_id = state
        
        # Get player and game names
        cur.execute("SELECT player_name FROM dim.dim_players WHERE player_id = %s;", (player_id,))
        player_name = cur.fetchone()[0]
        
        cur.execute("SELECT game_name, game_installment FROM dim.dim_games WHERE game_id = %s;", (game_id,))
        game_info = cur.fetchone()
        game_name = game_info[0]
        game_installment = game_info[1] if game_info[1] else ""
        full_game_name = f"{game_name}: {game_installment}" if game_installment else game_name
        
        # Count distinct games played (sessions)
        cur.execute("""
            SELECT COUNT(DISTINCT played_at) as games_played
            FROM fact.fact_game_stats
            WHERE player_id = %s AND game_id = %s;
        """, (player_id, game_id))
        games_played = cur.fetchone()[0]
        
        if games_played == 0:
            return jsonify({"facts": ["No stats recorded yet. Start playing to see educational stats!"], "games_played": 0}), 200
        
        # Get all stat types for this game
        cur.execute("""
            SELECT DISTINCT stat_type
            FROM fact.fact_game_stats
            WHERE player_id = %s AND game_id = %s AND stat_type IS NOT NULL;
        """, (player_id, game_id))
        stat_types = [row[0] for row in cur.fetchall()]
        
        # Generate facts based on tier
        facts = []
        
        # TIER 1: Basic Facts (1-2 games)
        if games_played >= 1:
            facts.extend(generate_basic_facts(cur, player_id, game_id, player_name, full_game_name, stat_types, timezone_str))
        
        # TIER 2: Descriptive Stats (3-30 games)
        if games_played >= 3:
            facts.extend(generate_descriptive_stats(cur, player_id, game_id, player_name, full_game_name, stat_types))
        
        # TIER 3: Advanced Stats (30+ games)
        if games_played > 30:
            facts.extend(generate_advanced_stats(cur, player_id, game_id, player_name, full_game_name, stat_types))
        
        response_data = {"facts": facts, "games_played": games_played}
        _cache_set(_ticker_cache_key, response_data, 200, ttl_seconds=900)  # 15 minutes
        return jsonify(response_data), 200

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error fetching stat ticker: {error}")
        if conn: conn.rollback()
        return jsonify({"error": str(error)}), 500
    finally:
        release_db_connection(conn)


def generate_basic_facts(cur, player_id, game_id, player_name, game_name, stat_types, timezone_str):
    """Generate basic facts: best performances, high scores"""
    facts = []
    
    for stat_type in stat_types[:3]:  # Limit to top 3 stat types
        # Best performance for this stat
        cur.execute("""
            SELECT stat_value, CAST(CONVERT_TIMEZONE(%s, played_at) AS DATE) as play_date
            FROM fact.fact_game_stats
            WHERE player_id = %s AND game_id = %s AND stat_type = %s
            ORDER BY stat_value DESC
            LIMIT 1;
        """, (timezone_str, player_id, game_id, stat_type))
        result = cur.fetchone()
        
        if result:
            best_value, best_date = result
            date_str = best_date.strftime('%B %d, %Y')
            facts.append(f"{player_name}'s best {stat_type} in {game_name} was {best_value} on {date_str}.")
    
    # High score across all stats
    cur.execute("""
        SELECT stat_type, MAX(stat_value) as high_score
        FROM fact.fact_game_stats
        WHERE player_id = %s AND game_id = %s
        GROUP BY stat_type
        ORDER BY high_score DESC
        LIMIT 1;
    """, (player_id, game_id))
    result = cur.fetchone()
    
    if result:
        stat_type, high_score = result
        facts.append(f"The highest {stat_type} recorded for {game_name} is {high_score}.")
    
    return facts


def generate_descriptive_stats(cur, player_id, game_id, player_name, game_name, stat_types):
    """Generate descriptive statistics: mean, median, mode, min, max, range"""
    facts = []
    
    for stat_type in stat_types[:2]:  # Top 2 stats
        # Get all values for calculations
        cur.execute("""
            SELECT stat_value
            FROM fact.fact_game_stats
            WHERE player_id = %s AND game_id = %s AND stat_type = %s
            ORDER BY stat_value;
        """, (player_id, game_id, stat_type))
        values = [row[0] for row in cur.fetchall()]
        
        if not values:
            continue
        
        # Calculate stats
        mean_val = round(sum(values) / len(values), 1)
        median_val = values[len(values) // 2] if len(values) % 2 == 1 else round((values[len(values)//2 - 1] + values[len(values)//2]) / 2, 1)
        min_val = min(values)
        max_val = max(values)
        range_val = max_val - min_val
        
        # Mode (most common value)
        from collections import Counter
        value_counts = Counter(values)
        mode_val = value_counts.most_common(1)[0][0]
        mode_count = value_counts.most_common(1)[0][1]
        
        # Generate fact sentences
        facts.append(f"On average, {player_name} gets {mean_val} {stat_type} per game in {game_name}.")
        facts.append(f"The median {stat_type} for {player_name} in {game_name} is {median_val}.")
        
        if mode_count > 1:
            facts.append(f"{player_name} most frequently scores {mode_val} {stat_type} in {game_name}.")
        
        facts.append(f"{player_name}'s {stat_type} in {game_name} ranges from {min_val} (minimum) to {max_val} (maximum).")
        facts.append(f"The range of {stat_type} scores in {game_name} is {range_val}.")
    
    return facts


def generate_advanced_stats(cur, player_id, game_id, player_name, game_name, stat_types):
    """Generate advanced statistics: percentile, standard deviation, variance"""
    facts = []
    
    for stat_type in stat_types[:2]:  # Top 2 stats
        # Get all values
        cur.execute("""
            SELECT stat_value
            FROM fact.fact_game_stats
            WHERE player_id = %s AND game_id = %s AND stat_type = %s
            ORDER BY stat_value;
        """, (player_id, game_id, stat_type))
        values = [row[0] for row in cur.fetchall()]
        
        if len(values) < 2:
            continue
        
        # Calculate advanced stats
        mean_val = sum(values) / len(values)
        
        # Variance and Standard Deviation
        variance = sum((x - mean_val) ** 2 for x in values) / len(values)
        std_dev = round(variance ** 0.5, 2)
        variance_rounded = round(variance, 2)
        
        # Percentiles (25th, 50th, 75th)
        def percentile(data, p):
            n = len(data)
            k = (n - 1) * p
            f = int(k)
            c = k - f
            if f + 1 < n:
                return data[f] + c * (data[f + 1] - data[f])
            return data[f]
        
        p25 = round(percentile(values, 0.25), 1)
        p50 = round(percentile(values, 0.50), 1)
        p75 = round(percentile(values, 0.75), 1)
        
        # Generate fact sentences
        facts.append(f"The standard deviation of {stat_type} in {game_name} is {std_dev}, showing {'high' if std_dev > mean_val * 0.3 else 'low'} variability in performance.")
        facts.append(f"The variance of {player_name}'s {stat_type} in {game_name} is {variance_rounded}.")
        facts.append(f"25% of {player_name}'s games have {stat_type} below {p25}, while 75% are below {p75}.")
        facts.append(f"The median (50th percentile) {stat_type} is {p50} for {player_name} in {game_name}.")
    
    return facts

"""
Flask endpoint additions for Instagram posting
"""

@app.route('/api/post_instagram', methods=['POST'])
@requires_api_key
def api_post_instagram():
    """
    Manually trigger Instagram post
    
    POST /api/post_instagram
    Headers: X-API-KEY
    Body (optional): {
        "player_id": 1,
        "force_type": "daily" | "historical"  // optional
    }
    """
    import sys
    sys.path.append(os.path.dirname(__file__))
    from instagram_poster import (
        get_db_connection, get_player_info, check_games_on_date,
        get_stats_for_date, detect_anomalies, get_historical_records_all_games,
        create_instagram_portrait_chart, post_to_instagram, generate_trendy_caption
    )
    from datetime import datetime, timedelta
    
    conn = None
    try:
        # Parse request
        data = request.get_json() or {}
        player_id = data.get('player_id', 1)
        force_type = data.get('force_type', None)  # 'daily', 'historical', or None
        
        # Connect to database
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cur = conn.cursor()
        
        # Get player info
        player_name, game_id, game_name, game_installment = get_player_info(cur, player_id)
        
        if not player_name or not game_id:
            return jsonify({"error": f"No player or game data found for player_id={player_id}"}), 404
        
        # Determine post content
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        timezone_str = os.environ.get("TIMEZONE", "America/Los_Angeles")
        
        post_type = None
        stats = []
        anomalies = []
        date_str = ""
        title = ""
        subtitle = None
        
        # Force specific type if requested
        if force_type == 'historical':
            post_type = 'historical'
            anomalies = get_historical_records_all_games(cur, player_id)
            stats = [(record['stat'], record['value']) for record in anomalies[:3]]
            title = "Historical Best Performances"
            subtitle = "All-Time Records"
        
        elif force_type == 'daily':
            if check_games_on_date(cur, player_id, today):
                post_type = 'daily_stats'
                stats = get_stats_for_date(cur, player_id, game_id, today)
                anomalies = detect_anomalies(cur, player_id, game_id, today)
                date_str = today.strftime('%A, %B %d')
                title = "Today's Performance"
                subtitle = date_str
            else:
                return jsonify({"error": "No games played today"}), 400
        
        # Default priority logic
        else:
            if check_games_on_date(cur, player_id, today):
                post_type = 'daily_stats'
                stats = get_stats_for_date(cur, player_id, game_id, today)
                anomalies = detect_anomalies(cur, player_id, game_id, today)
                date_str = today.strftime('%A, %B %d')
                title = "Today's Performance"
                subtitle = date_str
            
            elif check_games_on_date(cur, player_id, yesterday):
                post_type = 'recent_stats'
                stats = get_stats_for_date(cur, player_id, game_id, yesterday)
                anomalies = detect_anomalies(cur, player_id, game_id, yesterday)
                date_str = yesterday.strftime('%A, %B %d')
                title = "Yesterday's Performance"
                subtitle = date_str
            
            else:
                post_type = 'historical'
                anomalies = get_historical_records_all_games(cur, player_id, game_id)
                stats = [(record['stat'], record['value']) for record in anomalies[:3]]
                title = "Historical Best Performances"
                subtitle = "All-Time Records"
        
        if not stats:
            return jsonify({"error": "No stats available to post"}), 400
        
        # Create chart
        image_buffer = create_instagram_portrait_chart(
            stats, player_name, game_name, game_installment, title, subtitle
        )
        
        # Generate caption
        caption = generate_trendy_caption(post_type, stats, anomalies, player_name, game_name, date_str)
        
        # Post to Instagram
        success = post_to_instagram(image_buffer, caption)
        
        if success:
            return jsonify({
                "success": True,
                "message": "Posted to Instagram successfully",
                "post_type": post_type,
                "stats": stats,
                "caption": caption[:200] + "..."
            }), 200
        else:
            return jsonify({"error": "Failed to post to Instagram"}), 500
    
    except Exception as e:
        print(f"Error in Instagram posting: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
    finally:
        if conn:
            conn.close()


@app.route('/api/preview_instagram', methods=['GET'])
@requires_api_key
def api_preview_instagram():
    """
    Preview what would be posted to Instagram without actually posting
    
    GET /api/preview_instagram?player_id=1
    Headers: X-API-KEY
    
    Returns: JSON with post preview info and base64 encoded image
    """
    import sys
    sys.path.append(os.path.dirname(__file__))
    from instagram_poster import (
        get_db_connection, get_player_info, check_games_on_date,
        get_stats_for_date, detect_anomalies, get_historical_records_all_games,
        create_instagram_portrait_chart, generate_trendy_caption
    )
    from datetime import datetime, timedelta
    import base64
    
    conn = None
    try:
        player_id = request.args.get('player_id', 1, type=int)
        
        # Connect to database
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cur = conn.cursor()
        
        # Get player info
        player_name, game_id, game_name, game_installment = get_player_info(cur, player_id)
        
        if not player_name or not game_id:
            return jsonify({"error": f"No player or game data found for player_id={player_id}"}), 404
        
        # Determine post content
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        post_type = None
        stats = []
        anomalies = []
        date_str = ""
        title = ""
        subtitle = None
        
        if check_games_on_date(cur, player_id, today):
            post_type = 'daily_stats'
            stats = get_stats_for_date(cur, player_id, game_id, today)
            anomalies = detect_anomalies(cur, player_id, game_id, today)
            date_str = today.strftime('%A, %B %d')
            title = "Today's Performance"
            subtitle = date_str
        
        elif check_games_on_date(cur, player_id, yesterday):
            post_type = 'recent_stats'
            stats = get_stats_for_date(cur, player_id, game_id, yesterday)
            anomalies = detect_anomalies(cur, player_id, game_id, yesterday)
            date_str = yesterday.strftime('%A, %B %d')
            title = "Yesterday's Performance"
            subtitle = date_str
        
        else:
            post_type = 'historical'
            anomalies = get_historical_records_all_games(cur, player_id)
            stats = [(record['stat'], record['value']) for record in anomalies[:3]]
            title = "Historical Best Performances"
            subtitle = "All-Time Records"
        
        if not stats:
            return jsonify({"error": "No stats available"}), 400
        
        # Create chart
        image_buffer = create_instagram_portrait_chart(
            stats, player_name, game_name, game_installment, title, subtitle
        )
        
        # Generate caption
        caption = generate_trendy_caption(post_type, stats, anomalies, player_name, game_name, date_str)
        
        # Convert image to base64
        image_base64 = base64.b64encode(image_buffer.getvalue()).decode('utf-8')
        
        return jsonify({
            "post_type": post_type,
            "player_name": player_name,
            "game_name": game_name,
            "stats": stats,
            "anomalies": [a['description'] for a in anomalies] if anomalies else [],
            "caption": caption,
            "title": title,
            "subtitle": subtitle,
            "image_base64": image_base64,
            "image_format": "png"
        }), 200
    
    except Exception as e:
        print(f"Error in Instagram preview: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
    finally:
        if conn:
            conn.close()

# Timestamp of the last Redshift warmup ping — throttled to once per 10 minutes
# so bots/crawlers can't trigger repeated cold-start billing cycles.
_last_redshift_warmup: float = 0.0
_WARMUP_INTERVAL = 600  # seconds

# ── Bolt AI endpoint ─────────────────────────────────────────────────────────
@app.route('/api/ask', methods=['POST'])
@requires_jwt_auth
def ask_bolt(user_email):
    """Natural language stat queries powered by Gemini (Bolt AI panel)."""
    if not os.environ.get("GEMINI_API_KEY"):
        return jsonify({"reply": "Bolt isn't configured yet — add GEMINI_API_KEY to enable AI features."}), 200
    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400
    try:
        from utils.ai_utils import ask_agent
        reply = ask_agent(prompt)
        return jsonify({"reply": reply})
    except Exception as e:
        print(f"[Bolt] Error: {e}")
        return jsonify({"reply": "Something went wrong on my end. Try again in a moment."}), 200

# Health check endpoint
@app.route('/api/get_summary/<int:game_id>', methods=['GET'])
@requires_jwt_auth
def get_summary(user_email, game_id):
    """
    Return Today's Average and All-Time Best KPIs for the top 3 stat types.
    Query params: player_name (required), game_mode (optional filter).
    """
    player_name = request.args.get('player_name', '').strip()
    game_mode   = request.args.get('game_mode', '').strip() or None

    if not player_name:
        return jsonify({"error": "player_name is required"}), 400

    lower_is_better_kws = {'respawn', 'damage taken', 'loss', 'missed'}

    def is_lower_better(stat_type):
        return any(kw in stat_type.lower() for kw in lower_is_better_kws)

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Resolve player_id
        cur.execute("SELECT player_id FROM dim.dim_players WHERE player_name = %s;", (player_name,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Player not found"}), 404
        player_id = row[0]

        # Top 3 stat types — consistent with pipeline ordering
        mode_clause = "AND game_mode = %s" if game_mode else ""
        base_params = (player_id, game_id) + ((game_mode,) if game_mode else ())

        cur.execute(f"""
            SELECT stat_type
            FROM fact.fact_game_stats
            WHERE player_id = %s AND game_id = %s AND stat_type IS NOT NULL
            {mode_clause}
            GROUP BY stat_type
            HAVING AVG(stat_value) > 0
            ORDER BY AVG(stat_value) ASC
            LIMIT 3;
        """, base_params)
        top_stats = [r[0] for r in cur.fetchall()]

        if not top_stats:
            return jsonify({"today_avg": [], "all_time_best": []}), 200

        placeholders = ','.join(['%s'] * len(top_stats))
        stat_params  = tuple(top_stats) + ((game_mode,) if game_mode else ())

        # Today's average — PST-adjusted date comparison
        cur.execute(f"""
            SELECT stat_type, ROUND(AVG(stat_value)) AS avg_val
            FROM fact.fact_game_stats
            WHERE player_id = %s AND game_id = %s
              AND stat_type IN ({placeholders})
              AND CAST(CONVERT_TIMEZONE('UTC', 'America/Los_Angeles', played_at) AS DATE)
                  = CAST(CONVERT_TIMEZONE('UTC', 'America/Los_Angeles', GETDATE()) AS DATE)
              {mode_clause}
            GROUP BY stat_type;
        """, (player_id, game_id) + stat_params)
        today_avg = [
            {"stat_type": r[0], "value": int(r[1]), "lower_is_better": is_lower_better(r[0])}
            for r in cur.fetchall()
        ]

        # All-time best — MAX for normal stats, MIN for lower-is-better
        cur.execute(f"""
            SELECT stat_type, MAX(stat_value) AS max_val, MIN(stat_value) AS min_val
            FROM fact.fact_game_stats
            WHERE player_id = %s AND game_id = %s
              AND stat_type IN ({placeholders})
              {mode_clause}
            GROUP BY stat_type;
        """, (player_id, game_id) + stat_params)
        all_time_best = []
        for r in cur.fetchall():
            lib      = is_lower_better(r[0])
            best_val = r[2] if lib else r[1]   # MIN or MAX
            all_time_best.append({
                "stat_type": r[0],
                "value": int(best_val) if float(best_val) == int(best_val) else round(float(best_val), 1),
                "lower_is_better": lib,
            })

        # Statistical significance — pull all historical values for CI + z-score
        cur.execute(f"""
            SELECT stat_type, stat_value
            FROM fact.fact_game_stats
            WHERE player_id = %s AND game_id = %s
              AND stat_type IN ({placeholders})
              {mode_clause}
            ORDER BY stat_type;
        """, (player_id, game_id) + stat_params)
        hist_by_type = defaultdict(list)
        for r in cur.fetchall():
            hist_by_type[r[0]].append(float(r[1]))

        def _ci_and_z(values, today_val=None):
            """Return (ci_low, ci_high, z_score, n) for a list of historical values."""
            n = len(values)
            if n < 3:
                return None, None, None, n
            arr = np.array(values, dtype=float)
            sem = float(scipy_stats.sem(arr))
            if sem == 0:
                return None, None, None, n
            ci = scipy_stats.t.interval(0.95, n - 1, loc=float(np.mean(arr)), scale=sem)
            z = None
            if today_val is not None:
                std = float(np.std(arr, ddof=1))
                z = round((today_val - float(np.mean(arr))) / std, 2) if std > 0 else 0.0
            return round(float(ci[0]), 1), round(float(ci[1]), 1), z, n

        today_avg_out = []
        for stat in today_avg:
            ci_low, ci_high, z, n = _ci_and_z(hist_by_type.get(stat["stat_type"], []), stat["value"])
            today_avg_out.append({**stat, "ci_low": ci_low, "ci_high": ci_high, "n_sessions": n, "today_z_score": z})

        all_time_best_out = []
        for stat in all_time_best:
            ci_low, ci_high, _, n = _ci_and_z(hist_by_type.get(stat["stat_type"], []))
            all_time_best_out.append({**stat, "ci_low": ci_low, "ci_high": ci_high, "n_sessions": n})

        return jsonify({"today_avg": today_avg_out, "all_time_best": all_time_best_out}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_connection(conn)


@app.route('/api/get_interactive_chart/<int:game_id>', methods=['GET'])
@requires_jwt_auth
def get_interactive_chart(user_email, game_id):
    """
    Generate and return an interactive Plotly HTML chart for the given player/game.
    Returns raw HTML — embed via iframe srcdoc on the frontend (no GCS upload).
    Query params: player_name (required), game_mode (optional).
    """
    player_name = request.args.get('player_name', '').strip()
    game_mode   = request.args.get('game_mode', '').strip() or None

    if not player_name:
        return jsonify({"error": "player_name is required"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Resolve player_id
        cur.execute("SELECT player_id FROM dim.dim_players WHERE player_name = %s;", (player_name,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Player not found"}), 404
        player_id = row[0]

        # Resolve game info
        cur.execute("SELECT game_name, game_installment FROM dim.dim_games WHERE game_id = %s;", (game_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Game not found"}), 404
        game_name, game_installment = row[0], row[1]

        # Total sessions
        cur.execute("""
            SELECT COUNT(DISTINCT played_at) FROM fact.fact_game_stats
            WHERE player_id = %s AND game_id = %s;
        """, (player_id, game_id))
        games_played = cur.fetchone()[0]

        if games_played == 0:
            return jsonify({"error": "No stats found for this game"}), 404

        # Top 3 stat types
        cur.execute("""
            SELECT stat_type, AVG(stat_value) as avg_value
            FROM fact.fact_game_stats
            WHERE player_id = %s AND game_id = %s AND stat_type IS NOT NULL
            GROUP BY stat_type HAVING AVG(stat_value) > 0
            ORDER BY avg_value ASC LIMIT 3;
        """, (player_id, game_id))
        top_stats = [r[0] for r in cur.fetchall()]

        if games_played == 1:
            cur.execute("""
                SELECT stat_type, stat_value FROM fact.fact_game_stats
                WHERE player_id = %s AND game_id = %s
                ORDER BY played_at DESC LIMIT 3;
            """, (player_id, game_id))
            data = {}
            for i, (stype, sval) in enumerate(cur.fetchall(), 1):
                data[f'stat{i}'] = {'label': stype, 'value': sval, 'prev_value': None}
            chart_type = 'bar'
        else:
            data = get_stat_history_from_db(cur, player_id, game_id, top_stats, days_back=365)
            chart_type = 'line'

        html_bytes = generate_interactive_chart(
            chart_type, data, player_name, game_name,
            game_installment=game_installment, game_mode=game_mode
        )
        return html_bytes, 200, {'Content-Type': 'text/html; charset=utf-8'}

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_connection(conn)


@app.route('/api/download_chart', methods=['POST'])
@requires_jwt_auth
def download_chart(user_email):
    """Generate and stream a chart PNG for the given player/game/platform."""
    data = request.get_json(silent=True) or {}
    game_id    = data.get('game_id')
    player_name = data.get('player_name', '').strip()
    platform   = data.get('platform', 'twitter')

    if not all([game_id, player_name]):
        return jsonify({"error": "Missing game_id or player_name"}), 400
    if platform not in ('twitter', 'instagram'):
        return jsonify({"error": "platform must be 'twitter' or 'instagram'"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Resolve player_id
        cur.execute("SELECT player_id FROM dim.dim_players WHERE player_name = %s;", (player_name,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Player not found"}), 404
        player_id = row[0]

        # Resolve game info
        cur.execute("SELECT game_name, game_installment FROM dim.dim_games WHERE game_id = %s;", (game_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Game not found"}), 404
        game_name, game_installment = row[0], row[1]

        # Most recent game mode
        cur.execute("""
            SELECT game_mode FROM fact.fact_game_stats
            WHERE player_id = %s AND game_id = %s
            ORDER BY played_at DESC LIMIT 1;
        """, (player_id, game_id))
        row = cur.fetchone()
        game_mode = row[0] if row else None

        # Total sessions
        cur.execute("""
            SELECT COUNT(DISTINCT played_at) FROM fact.fact_game_stats
            WHERE player_id = %s AND game_id = %s;
        """, (player_id, game_id))
        games_played = cur.fetchone()[0]

        if games_played == 0:
            return jsonify({"error": "No stats found for this game"}), 404

        if games_played == 1:
            cur.execute("""
                SELECT stat_type, stat_value FROM fact.fact_game_stats
                WHERE player_id = %s AND game_id = %s
                ORDER BY played_at DESC LIMIT 3;
            """, (player_id, game_id))
            stat_data = {}
            for i, (stype, sval) in enumerate(cur.fetchall(), 1):
                stat_data[f'stat{i}'] = {'label': stype, 'value': sval, 'prev_value': None}
            image_buffer = generate_bar_chart(
                stat_data, player_name, game_name, game_installment,
                size=platform, game_mode=game_mode
            )
        else:
            cur.execute("""
                SELECT stat_type FROM fact.fact_game_stats
                WHERE player_id = %s AND game_id = %s AND stat_type IS NOT NULL
                GROUP BY stat_type HAVING AVG(stat_value) > 0
                ORDER BY AVG(stat_value) ASC LIMIT 3;
            """, (player_id, game_id))
            top_stats = [r[0] for r in cur.fetchall()]
            stat_history = get_stat_history_from_db(cur, player_id, game_id, top_stats, days_back=365)
            image_buffer = generate_line_chart(
                stat_history, player_name, game_name, game_installment,
                size=platform, game_mode=game_mode
            )

        image_buffer.seek(0)
        filename = f"{player_name}_{game_name}_{platform}.png".replace(' ', '_')
        return send_file(image_buffer, mimetype='image/png',
                         as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_connection(conn)


@app.route('/api/get_heatmap/<int:game_id>', methods=['GET'])
@requires_jwt_auth
def get_heatmap(user_email, game_id):
    """
    Returns session frequency by day-of-week and hour-of-day (PST).
    Used to render a time-heatmap showing when the player is most active.
    Query params: player_name (required).
    # Supabase migration note: replace CONVERT_TIMEZONE(...) with
    #   played_at AT TIME ZONE 'America/Los_Angeles'
    """
    player_name = request.args.get('player_name', '').strip()
    if not player_name:
        return jsonify({"error": "player_name is required"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT player_id FROM dim.dim_players WHERE player_name = %s;", (player_name,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Player not found"}), 404
        player_id = row[0]

        cur.execute("""
            SELECT
                EXTRACT(DOW  FROM CONVERT_TIMEZONE('UTC', 'America/Los_Angeles', played_at))::int AS dow,
                EXTRACT(HOUR FROM CONVERT_TIMEZONE('UTC', 'America/Los_Angeles', played_at))::int AS hour,
                COUNT(*) AS session_count
            FROM fact.fact_game_stats
            WHERE player_id = %s AND game_id = %s
            GROUP BY 1, 2
            ORDER BY 1, 2;
        """, (player_id, game_id))

        cells = [
            {"dow": r[0], "hour": r[1], "session_count": int(r[2])}
            for r in cur.fetchall()
        ]
        max_sessions = max((c["session_count"] for c in cells), default=0)
        return jsonify({"cells": cells, "max_sessions": max_sessions}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_connection(conn)


@app.route('/api/get_streaks/<int:game_id>', methods=['GET'])
@requires_jwt_auth
def get_streaks(user_email, game_id):
    """
    Returns current streak, longest streak, last session date, and total session days
    for a given player + game combination.
    Query params: player_name (required).
    # Supabase migration note: replace CONVERT_TIMEZONE(...) with
    #   played_at AT TIME ZONE 'America/Los_Angeles'
    """
    player_name = request.args.get('player_name', '').strip()
    if not player_name:
        return jsonify({"error": "player_name is required"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT player_id FROM dim.dim_players WHERE player_name = %s;", (player_name,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Player not found"}), 404
        player_id = row[0]

        cur.execute("""
            SELECT DISTINCT
                CAST(CONVERT_TIMEZONE('UTC', 'America/Los_Angeles', played_at) AS DATE) AS session_date
            FROM fact.fact_game_stats
            WHERE player_id = %s AND game_id = %s
            ORDER BY session_date DESC;
        """, (player_id, game_id))

        from datetime import date, timedelta
        dates = [r[0] for r in cur.fetchall()]   # list of date objects, newest first

        if not dates:
            return jsonify({
                "current_streak": 0, "longest_streak": 0,
                "last_session": None, "total_session_days": 0,
            }), 200

        # Current streak: consecutive days going back from today or yesterday
        today = date.today()
        current_streak = 0
        if dates[0] >= today - timedelta(days=1):
            expected = dates[0]
            for d in dates:
                if d == expected:
                    current_streak += 1
                    expected -= timedelta(days=1)
                else:
                    break

        # Longest streak (ascending order)
        asc = sorted(dates)
        longest = run = 1
        for i in range(1, len(asc)):
            if (asc[i] - asc[i - 1]).days == 1:
                run += 1
                longest = max(longest, run)
            else:
                run = 1

        return jsonify({
            "current_streak": current_streak,
            "longest_streak": max(current_streak, longest),
            "last_session": dates[0].isoformat(),
            "total_session_days": len(dates),
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_connection(conn)


@app.route('/api/get_ticker_facts/<int:game_id>', methods=['GET'])
@requires_jwt_auth
def get_ticker_facts(user_email, game_id):
    """
    Returns tiered educational stat facts for the Summary page ticker.
    Replaces the OBS-gated get_stat_ticker with JWT auth and player_name param.
    Tiers (same as OBS version):
    - 1-2 sessions:  basic facts (best value, high score)
    - 3-30 sessions: + descriptive stats (mean, median, mode, range)
    - 30+ sessions:  + advanced stats (std dev, variance, percentiles)
    Query params: player_name (required)
    # Supabase migration note: replace CONVERT_TIMEZONE(...) with
    #   played_at AT TIME ZONE 'America/Los_Angeles' in generate_basic_facts
    """
    player_name = request.args.get('player_name', '').strip()
    if not player_name:
        return jsonify({"error": "player_name is required"}), 400

    _cache_key = f"ticker_facts_{game_id}_{player_name}"
    _cached = _cache_get(_cache_key)
    if _cached:
        return jsonify(_cached[0]), _cached[1]

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT game_name, game_installment
            FROM dim.dim_games
            WHERE game_id = %s;
        """, (game_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Game not found"}), 404
        game_name, game_installment = row
        full_game_name = f"{game_name}: {game_installment}" if game_installment else game_name

        cur.execute("""
            SELECT player_id FROM dim.dim_players WHERE player_name = %s LIMIT 1;
        """, (player_name,))
        p = cur.fetchone()
        if not p:
            return jsonify({"error": "Player not found"}), 404
        player_id = p[0]

        cur.execute("""
            SELECT COUNT(DISTINCT played_at) FROM fact.fact_game_stats
            WHERE player_id = %s AND game_id = %s;
        """, (player_id, game_id))
        sessions = cur.fetchone()[0]

        if sessions == 0:
            return jsonify({"facts": [], "sessions": 0}), 200

        cur.execute("""
            SELECT DISTINCT stat_type FROM fact.fact_game_stats
            WHERE player_id = %s AND game_id = %s AND stat_type IS NOT NULL;
        """, (player_id, game_id))
        stat_types = [r[0] for r in cur.fetchall()]

        facts = []
        if sessions >= 1:
            facts.extend(generate_basic_facts(cur, player_id, game_id, player_name, full_game_name, stat_types, 'America/Los_Angeles'))
        if sessions >= 3:
            facts.extend(generate_descriptive_stats(cur, player_id, game_id, player_name, full_game_name, stat_types))
        if sessions > 30:
            facts.extend(generate_advanced_stats(cur, player_id, game_id, player_name, full_game_name, stat_types))

        result = {"facts": facts, "sessions": sessions}
        _cache_set(_cache_key, result, 200, ttl_seconds=900)
        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_connection(conn)


@app.route('/health', methods=['GET'])
def health_check():
    # Fire a background Redshift ping to pre-warm the connection pool.
    # Throttled to once per 10 minutes to avoid unnecessary RPU billing.
    global _last_redshift_warmup
    now = time.monotonic()
    if now - _last_redshift_warmup >= _WARMUP_INTERVAL:
        _last_redshift_warmup = now
        def _warm_redshift():
            try:
                conn = get_db_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                    release_db_connection(conn)
            except Exception:
                pass
        threading.Thread(target=_warm_redshift, daemon=True).start()
    return jsonify({"status": "healthy"}), 200

@app.route('/db_health', methods=['GET'])
def db_health_check():
    # NOTE: Does NOT query Redshift — use /health for keep-alive pings.
    # Only call this manually to confirm DB credentials are reachable.
    # Frequent polling of this endpoint keeps Redshift active and drives up RPU costs.
    pool_ok = db_pool is not None
    return jsonify({
        "status": "healthy" if pool_ok else "pool_uninitialized",
        "db_connection": "pool_ready" if pool_ok else "pool not yet initialized — will connect on first request"
    }), 200

def test_ssl_connection():
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT ssl_is_used();")
            ssl_status = cur.fetchone()
            print(f"✅ SSL Connection Status: {ssl_status}")
            cur.close()
        except Exception as e:
            print(f"⚠️ Could not verify SSL status: {e}")
        finally:
            release_db_connection(conn)

if __name__ == '__main__':
     # Initialize pool once
    initialize_db_pool()
    
    # Create tables
    create_tables()

    # test_ssl_connection()
    app.run(debug=True, 
            host='0.0.0.0', 
            port=int(os.environ.get("PORT", 5000)),
            use_reloader=False  # ← Disable auto-reloader in development
            )