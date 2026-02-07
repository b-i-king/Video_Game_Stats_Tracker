import os
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2 import sql
from flask import Flask, request, jsonify, send_file
from datetime import datetime, timedelta, timezone
import jwt
from flask_cors import CORS
import atexit
from utils.chart_utils import generate_bar_chart, generate_line_chart, get_stat_history_from_db
from utils.gcs_utils import upload_chart_to_gcs
from utils.ifttt_utils import trigger_ifttt_post, generate_post_caption

app = Flask(__name__)
CORS(app)

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

if not all([DB_URL, DB_NAME, DB_USER, DB_PASSWORD, API_KEY, JWT_SECRET_KEY]):
    print("WARNING: One or more environment variables are not set. Using default values.")
if not TRUSTED_EMAILS_LIST:
    print("WARNING: TRUSTED_EMAILS environment variable is not set or empty. No users will be automatically marked as trusted.")

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
            minconn=1,      # Keep low for development
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

def release_db_connection(conn):
    """Returns a connection to the pool."""
    global db_pool
    if db_pool and conn:
        db_pool.putconn(conn)
        
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
                game_level INTEGER,
                win INTEGER,
                ranked INTEGER,
                pre_match_rank_value VARCHAR(50),
                post_match_rank_value VARCHAR(50),
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
             return jsonify({"message": f"User {user_email} already exists."}), 200

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

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get the user_id from the authenticated email
        cur.execute("SELECT user_id, is_trusted FROM dim.dim_users WHERE user_email = %s;", (user_email,))
        user_result = cur.fetchone()
        if not user_result: return jsonify({"error": "Authenticated user not found."}), 404
        user_id, is_trusted = user_result
        if not is_trusted: return jsonify({"error": "User not authorized"}), 403

         # --- Game Handling ---
        # Handle NULL game_installment properly
        if game_installment:
            cur.execute("SELECT game_id FROM dim.dim_games WHERE game_name = %s AND game_installment = %s;", (game_name, game_installment))
        else:
            cur.execute("SELECT game_id FROM dim.dim_games WHERE game_name = %s AND game_installment IS NULL;", (game_name,))
        
        game_record = cur.fetchone()
        game_id = None
        if not game_record:
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

        # --- Player Handling (Redshift Safe) ---
        cur.execute("SELECT player_id FROM dim.dim_players WHERE player_name = %s AND user_id = %s;", (player_name, user_id))
        player_record = cur.fetchone()
        player_id = None
        if not player_record:
            print(f"Player '{player_name}' for user {user_id} not found, creating.")
            cur.execute("INSERT INTO dim.dim_players (player_name, user_id, created_at) VALUES (%s, %s, GETDATE());", (player_name, user_id))
            conn.commit()
            cur.execute("SELECT player_id FROM dim.dim_players WHERE player_name = %s AND user_id = %s;", (player_name, user_id))
            player_id_result = cur.fetchone()
            if not player_id_result: raise Exception("Failed to get player_id after insert.")
            player_id = player_id_result[0]
        else:
            player_id = player_record[0]

        # --- Stat Insertion ---
        successful_inserts = 0
        for stat_record in stats:
            if not stat_record.get('stat_type') or stat_record.get('stat_value') is None: continue
            cur.execute("""
                INSERT INTO fact.fact_game_stats
                (game_id, player_id, stat_type, stat_value, game_mode, game_level, win, ranked, pre_match_rank_value, post_match_rank_value, played_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, GETDATE());
            """, (
                game_id, player_id, stat_record.get('stat_type'), stat_record.get('stat_value'),
                stat_record.get('game_mode'), stat_record.get('game_level'), stat_record.get('win'),
                stat_record.get('ranked'), stat_record.get('pre_match_rank_value'), stat_record.get('post_match_rank_value')
            ))
            successful_inserts += 1
        if successful_inserts > 0:
            conn.commit()
            print(f"✅ {successful_inserts} stats inserted successfully")
            
            # --- SOCIAL MEDIA INTEGRATION ---
            try:
                # Count total games played for this player/game
                cur.execute("""
                    SELECT COUNT(DISTINCT played_at) as games_played
                    FROM fact.fact_game_stats
                    WHERE player_id = %s AND game_id = %s;
                """, (player_id, game_id))
                games_played = cur.fetchone()[0]
                
                print(f"📊 Generating chart for social media (Games played: {games_played})...")
                
                # Get top 3 stat types for this game
                cur.execute("""
                    SELECT stat_type, AVG(stat_value) as avg_value
                    FROM fact.fact_game_stats
                    WHERE game_id = %s AND stat_type IS NOT NULL
                    GROUP BY stat_type
                    HAVING AVG(stat_value) > 0
                    ORDER BY avg_value ASC
                    LIMIT 3;
                """, (game_id,))
                top_stats = [row[0] for row in cur.fetchall()]
                
                if games_played == 1:
                    # Generate BAR CHART (first game)
                    # Get current stats for bar chart
                    stat_data = {}
                    for i, stat_type in enumerate(top_stats[:3], 1):
                        cur.execute("""
                            SELECT stat_value FROM fact.fact_game_stats
                            WHERE player_id = %s AND game_id = %s AND stat_type = %s
                            ORDER BY played_at DESC LIMIT 1;
                        """, (player_id, game_id, stat_type))
                        result = cur.fetchone()
                        stat_data[f'stat{i}'] = {
                            'label': stat_type,
                            'value': result[0] if result else 0
                        }
                    
                    image_buffer = generate_bar_chart(stat_data, player_name, game_name, game_installment)
                    chart_type = 'bar'
                    
                elif games_played > 1:
                    # Generate LINE CHART (multiple games)
                    stat_history = get_stat_history_from_db(cur, player_id, game_id, top_stats)
                    image_buffer = generate_line_chart(stat_history, player_name, game_name, game_installment)
                    chart_type = 'line'
                
                # Upload to Google Cloud Storage
                public_url = upload_chart_to_gcs(image_buffer, player_name, game_name, chart_type)
                
                if public_url:
                    # Generate caption
                    caption = generate_post_caption(
                        player_name, 
                        game_name, 
                        game_installment, 
                        stat_data if games_played == 1 else stat_history,
                        games_played,
                        is_live
                    )
                    
                    # Trigger IFTTT webhook
                    social_platform = os.environ.get('SOCIAL_MEDIA_PLATFORM', 'twitter')  # 'twitter', 'instagram', or 'both'
                    success = trigger_ifttt_post(public_url, caption, social_platform)
                    
                    if success:
                        print(f"✅ Social media post triggered successfully!")
                    else:
                        print(f"⚠️ Social media post failed, but stats were saved")
                else:
                    print(f"⚠️ Failed to upload chart, but stats were saved")
                    
            except Exception as social_error:
                # Don't fail the entire request if social media posting fails
                print(f"⚠️ Social media integration error (stats still saved): {social_error}")
            
            return jsonify({"message": f"Stats successfully added ({successful_inserts} records)!"}), 201

        else:
            return jsonify({"error": "No valid stats provided to insert."}), 400
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error: {error}"); conn.rollback()
        return jsonify({"error": f"An internal error occurred: {str(error)}"}), 500
    finally:
        release_db_connection(conn)

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
            SELECT DISTINCT g.game_id, g.game_name
            FROM dim.dim_games g
            JOIN fact.fact_game_stats gs ON g.game_id = gs.game_id
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            WHERE p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = %s)
            ORDER BY g.game_name;
        """, (user_email,))
        games = [{"game_id": row[0], "game_name": row[1]} for row in cur.fetchall()]
        return jsonify({"games": games}), 200
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error while fetching games for user {user_email}: {error}")
        return jsonify({"error": "An error occurred while fetching games."}), 500
    finally:
        if conn: conn.close()

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

    # 2. Get timezone
    timezone_str = request.args.get('tz', 'UTC')
    
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
            # Get top 2 relevant stats (highest non-zero AVG, ascending)
            cur.execute("""
                SELECT stat_type, AVG(stat_value) as avg_value
                FROM fact.fact_game_stats
                WHERE game_id = %s 
                  AND stat_type IS NOT NULL 
                  AND stat_type != ''
                  AND stat_value > 0
                GROUP BY stat_type
                HAVING AVG(stat_value) > 0
                ORDER BY avg_value ASC
                LIMIT 2;
            """, (game_id,))
            top_stats = [row[0] for row in cur.fetchall()]
            include_wins = True
            print(f"Win tracking enabled. Top 2 relevant stats: {top_stats}")
        else:
            # Get top 3 relevant stats (highest non-zero AVG, ascending)
            cur.execute("""
                SELECT stat_type, AVG(stat_value) as avg_value
                FROM fact.fact_game_stats
                WHERE game_id = %s 
                  AND stat_type IS NOT NULL 
                  AND stat_type != ''
                  AND stat_value > 0
                GROUP BY stat_type
                HAVING AVG(stat_value) > 0
                ORDER BY avg_value ASC
                LIMIT 3;
            """, (game_id,))
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

        # Handle other stats
        for i, stat_type in enumerate(top_stats, stat_index):
            value = 0
            abbrev = abbreviate_stat(stat_type)
            
            # Use AVG for last day, SUM for today (or AVG if it makes more sense)
            if stats_today_exist:
                # For today, use SUM
                query = sql.SQL("""
                    SELECT SUM(stat_value)
                    FROM fact.fact_game_stats
                    WHERE player_id = %s AND game_id = %s AND stat_type = %s
                      AND CAST(CONVERT_TIMEZONE(%s, played_at) AS DATE) = %s;
                """)
                cur.execute(query, (player_id, game_id, stat_type, timezone_str, query_date))
            else:
                # For last day, use AVG
                query = sql.SQL("""
                    SELECT AVG(stat_value)
                    FROM fact.fact_game_stats
                    WHERE player_id = %s AND game_id = %s AND stat_type = %s
                      AND CAST(CONVERT_TIMEZONE(%s, played_at) AS DATE) = %s;
                """)
                cur.execute(query, (player_id, game_id, stat_type, timezone_str, query_date))

            result = cur.fetchone()
            if result and result[0] is not None:
                if stats_today_exist:
                    value = int(result[0])
                else:
                    value = round(float(result[0]))  # Round to whole number for cleaner look
            
            results[f'stat{i}'] = {"label": f"{abbrev}", "value": value}

        # Add time_period to response
        results['time_period'] = time_period
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

    timezone_str = request.args.get('tz', 'UTC')
    
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
        
        return jsonify({"facts": facts, "games_played": games_played}), 200
        
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

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/db_health', methods=['GET'])
def db_health_check():
    conn = None
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor(); cur.execute("SELECT 1;"); cur.fetchone()
            release_db_connection(conn)
            return jsonify({"status": "healthy", "db_connection": "successful"}), 200
        else:
            return jsonify({"status": "unhealthy", "db_connection": "failed to get from pool"}), 503
    except (Exception, psycopg2.DatabaseError) as e:
        print(f"DB health check failed: {e}")
        return jsonify({"status": "unhealthy", "db_connection": "failed query"}), 503
    finally:
        if conn: release_db_connection(conn)

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