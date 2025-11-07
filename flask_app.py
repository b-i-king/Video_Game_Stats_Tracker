import os
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from flask import Flask, request, jsonify
from datetime import datetime, timedelta, timezone
import streamlit as st
import jwt


app = Flask(__name__)

# --- Environment Variable Check ---
DB_URL = os.environ.get("DB_URL")
DB_NAME = os.environ.get("DB_NAME")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
API_KEY = os.environ.get("API_KEY") # Still needed for login and add_trusted_user
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
TRUSTED_EMAILS_STR = os.environ.get("TRUSTED_EMAILS", "")
TRUSTED_EMAILS_LIST = [email.strip() for email in TRUSTED_EMAILS_STR.split(',') if email.strip()]

TRUSTED_EMAILS_LIST = ["bking2415@gmail.com"]
# For local testing defaults
FLASK_API_URL = "http://127.0.0.1:5000/api"
DB_URL = "bol.671703419022.us-west-1.redshift-serverless.amazonaws.com"
DB_NAME = "game_stats_tracker"
DB_USER = "admin"
DB_PASSWORD = "King1993"
API_KEY = "your_secret_api_key_here"
JWT_SECRET_KEY = "sume_random_secret_key"


if not all([DB_URL, DB_NAME, DB_USER, DB_PASSWORD, API_KEY, JWT_SECRET_KEY]):
    print("WARNING: One or more environment variables are not set. Using default values.")
if not TRUSTED_EMAILS_LIST:
    print("WARNING: TRUSTED_EMAILS environment variable is not set or empty. No users will be automatically marked as trusted.")

# --- Database Connection Pool ---
# Create the connection pool once when the app starts
try:
    print("Initializing database connection pool...")
    db_pool = SimpleConnectionPool(
        minconn=1,  # Minimum number of connections to keep open
        maxconn=10, # Maximum number of connections
        host=DB_URL,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=5439, # Default Redshift port
        connect_timeout=10
    )
    print("Database connection pool initialized successfully.")
except (Exception, psycopg2.Error) as error:
    print(f"FATAL ERROR: Failed to initialize database connection pool: {error}")
    db_pool = None # Set to None to indicate failure
    
# def get_db_connection(database_url=DB_URL, db_name=DB_NAME, db_user=DB_USER, db_password=DB_PASSWORD):
#     """Establishes a connection to the PostgreSQL database."""
#     print("Connecting to database...")
#     # Basic validation
#     if not all([database_url, db_name, db_user, db_password]):
#         print("Error: Database connection details are missing.")
#         return None
#     try:
#         conn = psycopg2.connect(
#             host=database_url,
#             database=db_name,
#             user=db_user,
#             password=db_password,
#             port=5439
#         )
#         print("Successfully connected to the database.")
#         return conn
#     except (Exception, psycopg2.Error) as error:
#         print(f"Error connecting to the database: {error}")
#         return None

def get_db_connection():
    """Gets a connection from the pool."""
    if db_pool:
        try:
            # print("Getting connection from pool...")
            return db_pool.getconn()
        except (Exception, psycopg2.Error) as error:
            print(f"Error getting connection from pool: {error}")
            return None
    else:
        print("Error: Database pool is not initialized.")
        return None

def release_db_connection(conn):
    """Returns a connection to the pool."""
    if db_pool and conn:
        # print("Returning connection to pool...")
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
                game_name VARCHAR(255) NOT NULL UNIQUE,
                game_series VARCHAR(255),
                game_genre VARCHAR(255),
                game_subgenre VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS dim.dim_players (
                player_id INT IDENTITY(1, 1) PRIMARY KEY,
                player_name VARCHAR(255) NOT NULL UNIQUE,
                user_id INTEGER REFERENCES dim.dim_users(user_id) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP 
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
    game_series = data.get('game_series')
    game_genre = data.get('game_genre')
    game_subgenre = data.get('game_subgenre')
    player_name = data.get('player_name')
    stats = data.get('stats')
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

    if not all([game_name, player_name, stats]):
        return jsonify({"error": "Missing game_name, player_name, or stats"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get the user_id from the authenticated email
        cur.execute("SELECT user_id FROM dim.dim_users WHERE user_email = %s;", (user_email,))
        user_id_row = cur.fetchone()
        if not user_id_row:
            return jsonify({"error": "Authenticated user not found."}), 404
        user_id = user_id_row[0]

        # --- Handle Game ---
        cur.execute("SELECT game_id FROM dim.dim_games WHERE game_name = %s;", (game_name,))
        game_id_row = cur.fetchone()
        if not game_id_row:
            cur.execute(
                "INSERT INTO dim.dim_games (game_name, game_series, game_genre, game_subgenre) "
                "VALUES (%s, %s, %s, %s);",
                (game_name, game_series, game_genre, game_subgenre)
            )
            conn.commit()  # Commit before select to make sure insert is visible
            cur.execute("SELECT game_id FROM dim.dim_games WHERE game_name = %s;", (game_name,))
            game_id_row = cur.fetchone()
            if not game_id_row:
                raise Exception("Game insert failed.")
            game_id = game_id_row[0]
        else:
            game_id = game_id_row[0]
            cur.execute("UPDATE dim.dim_games SET last_played_at = CURRENT_TIMESTAMP WHERE game_id = %s;", (game_id,))

        # --- Handle Player ---
        cur.execute("SELECT player_id FROM dim.dim_players WHERE player_name = %s AND user_id = %s;", (player_name, user_id))
        player_id_row = cur.fetchone()
        if not player_id_row:
            cur.execute(
                "INSERT INTO dim.dim_players (player_name, user_id) VALUES (%s, %s);",
                (player_name, user_id)
            )
            conn.commit()
            cur.execute("SELECT player_id FROM dim.dim_players WHERE player_name = %s AND user_id = %s;", (player_name, user_id))
            player_id_row = cur.fetchone()
            if not player_id_row:
                raise Exception("Player insert failed.")
            player_id = player_id_row[0]
        else:
            player_id = player_id_row[0]

        # --- Insert Stats ---
        for stat_record in stats:
            cur.execute("""
                INSERT INTO fact.fact_game_stats (
                    game_id, player_id, stat_type, stat_value,
                    game_mode, game_level, win, ranked,
                    pre_match_rank_value, post_match_rank_value
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                game_id,
                player_id,
                stat_record.get('stat_type'),
                stat_record.get('stat_value'),
                stat_record.get('game_mode'),
                stat_record.get('game_level'),
                stat_record.get('win'),
                stat_record.get('ranked'),
                stat_record.get('pre_match_rank_value'),
                stat_record.get('post_match_rank_value')
            ))

        conn.commit()
        return jsonify({"message": "Stats successfully added!"}), 201

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error while adding stats: {error}")
        if conn:
            conn.rollback()
        return jsonify({"error": f"An error occurred while adding stats: {error}"}), 500

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
        cur.execute("SELECT game_name, game_series, game_genre, game_subgenre FROM dim.dim_games WHERE game_id = %s;", (game_id,))
        game = cur.fetchone()
        if not game:
            return jsonify({"error": "Game not found."}), 404
        
        game_details = {"game_name": game[0], "game_series": game[1], "game_genre": game[2], "game_subgenre": game[3]}
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
    game_series = data.get('game_series')
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
            SET game_name = %s, game_series = %s, game_genre = %s, game_subgenre = %s
            WHERE game_id = %s;
        """, (game_name, game_series, game_genre, game_subgenre, game_id))
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

@app.route('/api/get_player_games/<int:player_id>', methods=['GET'])
@requires_jwt_auth
def get_player_games_by_id(player_id, user_email):
    """Gets games (id, name) for a specific player, verifying user ownership."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT g.game_id, g.game_name
            FROM dim.dim_games g
            JOIN fact.fact_game_stats gs ON g.game_id = gs.game_id
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            WHERE p.player_id = %s
            AND p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = %s)
            ORDER BY g.game_name;
        """, (player_id, user_email))
        # Return list of dicts
        games = [{"game_id": row[0], "game_name": row[1]} for row in cur.fetchall()]
        return jsonify({"games": games}), 200
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error while fetching player games for player {player_id}: {error}")
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

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    create_tables()
    app.run(debug=True)