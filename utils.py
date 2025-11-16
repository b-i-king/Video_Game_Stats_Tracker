import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine

# --- Secrets and Config ---
FLASK_API_URL = st.secrets.flask.flask_api_url
DB_URL = st.secrets.redshift.database_url
DB_NAME = st.secrets.redshift.database_name
DB_USER = st.secrets.redshift.database_user 
DB_PASSWORD = st.secrets.redshift.database_password
API_KEY = st.secrets.config.api_key
TRUSTED_EMAILS = st.secrets.config.trusted_emails
YOUR_APP_HOME_URL = st.secrets.config.app_home_url
YOUR_PRIVACY_POLICY_URL = st.secrets.config.privacy_policy_url
YOUR_TERMS_OF_SERVICE_URL = st.secrets.config.terms_of_service_url

# --- Genre Data ---
GENRES = {
    "Select a Genre": ["Select a Subgenre"],
    "Action": ["First-Person Shooter (FPS)", "Third-Person Shooter (TPS)", "Beat'Em Up", "Fighting Game", "Stealth", "Action-Adventure", "Survival", "Loother Shooter", "Rhythm", "Battle Royale"],
    "Battle Royale": ["First-Person Shooter (FPS)", "Third-Person Shooter (TPS)", "Hero-Based", "Mobile", "Party"],
    "Role-Playing (RPG)": ["Action", "Western", "Japanese", "Tactical", "Open‑World", "MMO", "Roguelike", "Dungeon Crawler", "Monster-Taming"],
    "Massively Multiplayer Online RPGs (MMORPGs)": ["Theme-Park", "Sandbox", "Action", "Sci-Fi", "Fantasy", "Turn-Based", "Virtual-World", "Metaworld"],
    "Action RPGs": ["Hack-and-Slash", "Masher", "Soulslike", "TPS Hybrid", "First‑Person", "Hunting", "Roguelike", "MMO"],
    "Tacical RPGs": ["Grid-Based", "Western", "Roguelike", "Hybrid", "Real-Time"],
    "Simulation": ["Construction & Management (CMS)", "Business", "Life", "Vehicle", "Sports", "Tactical", "Other"],
    "Shooter": ["Military", "Tactical", "Arena", "Hero", "Looter", "Immersive Sim", "Retro", "Battle Royale", "Stealth"],
    "Stealth": ["Tactical Action", "Immersive Sim", "Disguise-Based", "Horror", "Top-Down", "Procedural"],
    "First‑Person Shooter (FPS)": ["Military", "Immersive Sim", "Hero"],
    "Platformers": ["Traditional 2D Side‑Scrolling", "Puzzle", "Run‑and‑Gun", "Exploration RPG", "Cinematic", "Collect‑and‑Complete", "Endless Runner"],
    "Strategy": ["Real-Time Strategy (RTS)", "Real-Time Tactics (RTT)", "Turn-Based Strategy (TBS)", "Turn-Based Tactics(TBT)", "Grand", "4X", "Tower Defense", "Auto Battler", "MMO", "Construction & Management (CMS)", "Wargame", "Hybrid"],
    "Survival": ["Open-World", "Simulation", "Horror", "Social", "Space", "Post-Apocalyptic", "Narrative", "Settlement"],
    "Sports": ["Arcade", "Simulation", "Management", "Mult-Sport", "Extreme", "Combat"],
    "Puzzle": ["Logic", "Trivia", "Tile-Matching", "Hidden Object", "Physics-Based", "Exploration", "Sokoban", "Construction", "Traditional", "Reveal-the-Picture"],
    "Adventure": ["Text", "Graphic", "Interactive Movie", "Real-Time 3D", "Visual Novel", "Walking Simulator", "Escape Room", "Puzzle"],
    "Action-Adventure": ["Cinematic", "Action RPG", "Open-World", "Metroidvania", "Survival Horror", "Stealth-Based", "Hack-and-Slash", "Grand Theft Auto"],
    "Fighting": ["2D Versus", "2.5D", "True 3D", "Anime", "Tag-Team", "Platform", "Weapon-Based"],
    "Real-Time Strategy (RTS)": ["Classic Base‑Building", "Tactical", "Grand-Scale", "Real‑Time Tactics (RTT)", "Hybrid", "Hero‑Based"],
    "Racing": ["Simulation‑Style", "Touring‑Car", "Arcade‑Style", "Kart", "Off-Road", "Futuristic", "Street", "Motorcycle", "Top-Down", "Combat"],
    "Casual": ["Tile‑Matching", "Hidden‑Object", "Hyper‑Casual", "Time‑Management", "Puzzle", "Simulation", "Street", "Card & Board", "Party Games & Minigame"],
    "Party": ["Mini-Game Collections", "Trivia", "Social Deduction", "Social Brawlers", "Rhythm & Music", "Collaborative", "Card & Board", "Guessing"]
}

# --- Authentication Logic ---
def attempt_flask_login(user_email):
    """Requests a JWT from the Flask backend and updates session state."""
    try:
        print(f"Attempting Flask login for user: {user_email}...")
        response = requests.post(
            f"{FLASK_API_URL}/login",
            headers={"X-API-KEY": API_KEY, "Content-Type": "application/json"},
            json={"email": user_email}
        )
        response.raise_for_status()
        token = response.json().get('token')
        is_trusted_from_backend = response.json().get('is_trusted', False)

        if token:
            print(f"Flask login successful. JWT received. Backend confirmed Trusted: {is_trusted_from_backend}")
            st.session_state.jwt_token = token
            st.session_state.is_trusted_user = is_trusted_from_backend
            st.session_state.is_registered_guest = not is_trusted_from_backend
            st.session_state.auth_mode = 'logged_in'
            st.session_state.email = user_email
            return True
        else:
             print(f"Flask login okay but no token for {user_email}. Backend Trusted: {is_trusted_from_backend}")
             st.session_state.is_trusted_user = False
             st.session_state.is_registered_guest = True
             st.session_state.auth_mode = 'logged_in'
             st.session_state.email = user_email
             st.session_state.jwt_token = None
             return False
    except requests.exceptions.RequestException as e:
        print(f"Flask login failed: Request Exception: {e}")
        error_detail = str(e)
        if 'response' in locals() and response is not None:
             try: error_detail = response.json().get("message", response.json().get("error", response.text))
             except ValueError: error_detail = response.text
        st.error(f"Failed to authenticate with backend: {error_detail}")
        st.session_state.auth_mode = 'login_failed'
        return False

def register_guest_user(user_email):
    """Registers a non-trusted user in the backend."""
    if not st.session_state.get('is_registered_guest', False):
        try:
            print(f"Registering guest user {user_email} in backend...")
            reg_response = requests.post(
                f"{FLASK_API_URL}/add_user",
                headers={"X-API-KEY": API_KEY, "Content-Type": "application/json"},
                json={"email": user_email}
            )
            reg_response.raise_for_status()
            print(f"Guest registration check completed (Status: {reg_response.status_code})")
            st.session_state.is_registered_guest = True
            st.session_state.is_trusted_user = False
            st.session_state.auth_mode = 'logged_in'
            st.session_state.email = user_email
            st.session_state.jwt_token = None
            return True
        except requests.exceptions.RequestException as e:
             print(f"Warning: Failed to ensure guest user registration: {e}")
             st.warning(f"Could not register your email with the backend: {e}")
             st.session_state.auth_mode = 'login_failed'
             return False
    else:
        st.session_state.is_trusted_user = False
        st.session_state.auth_mode = 'logged_in'
        st.session_state.email = user_email
        st.session_state.jwt_token = None
        return True

# --- Helper Functions ---

def get_auth_headers():
    """Returns the authorization headers with the JWT token, if available and user is trusted."""
    # Only return headers if user is trusted and has a token
    if st.session_state.is_trusted_user and st.session_state.jwt_token:
        return {"Authorization": f"Bearer {st.session_state.jwt_token}"}
    else:
        # print("get_auth_headers: No valid JWT token found or user not trusted.") # Debug
        return None

# --- Data fetching functions with caching ---
def get_all_players():
    """Fetches players (id, name) for the ldeleting individual stat entries (e.g., a single match).deleting individual stat entries (e.g., a single match).ogged-in user."""
    if not st.session_state.is_trusted_user: return []
    cache_key = f"players_{st.session_state.email}"
    if cache_key in st.session_state.data_cache: return st.session_state.data_cache[cache_key]
    auth_headers = get_auth_headers()
    if not auth_headers: st.error("Auth token missing for players."); return []
    try:
        response = requests.get(f"{FLASK_API_URL}/get_players", headers=auth_headers)
        if response.status_code == 401: st.error("Auth failed (players)."); st.session_state.jwt_token = None; st.session_state.auth_mode = 'guest'; st.rerun(); return []
        response.raise_for_status(); players = response.json().get('players', []); st.session_state.data_cache[cache_key] = players; return players
    except requests.exceptions.RequestException as e: st.error(f"Error fetching players: {e}"); return []

def get_all_games():
    """Fetches all games (id, name) the user has stats for."""
    if not st.session_state.is_trusted_user: return []
    cache_key = f"all_games_{st.session_state.email}"
    if cache_key in st.session_state.data_cache: return st.session_state.data_cache[cache_key]
    auth_headers = get_auth_headers()
    if not auth_headers: st.error("Auth token missing for games list."); return []
    try:
        response = requests.get(f"{FLASK_API_URL}/get_games", headers=auth_headers)
        if response.status_code == 401: st.error("Auth failed (games list)."); st.session_state.jwt_token = None; st.session_state.auth_mode = 'guest'; st.rerun(); return []
        response.raise_for_status(); games = response.json().get('games', []); st.session_state.data_cache[cache_key] = games; return games
    except requests.exceptions.RequestException as e: st.error(f"Error fetching games list: {e}"); return []

def get_game_details(game_id):
    """Fetches details for a single game."""
    if not st.session_state.is_trusted_user or not game_id: return None
    cache_key = f"game_details_{game_id}"
    if cache_key in st.session_state.data_cache: return st.session_state.data_cache[cache_key]
    auth_headers = get_auth_headers()
    if not auth_headers: st.error("Auth token missing for game details."); return None
    try:
        response = requests.get(f"{FLASK_API_URL}/get_game_details/{game_id}", headers=auth_headers)
        if response.status_code == 401: st.error("Auth failed (game details)."); st.session_state.jwt_token = None; st.session_state.auth_mode = 'guest'; st.rerun(); return None
        response.raise_for_status(); details = response.json(); st.session_state.data_cache[cache_key] = details; return details
    except requests.exceptions.RequestException as e: st.error(f"Error fetching game details for {game_id}: {e}"); return None

def get_game_ranks(game_id):
    if not st.session_state.is_trusted_user or not game_id: return []
    cache_key = f"game_ranks_{st.session_state.email}_{game_id}"
    if cache_key in st.session_state.data_cache: return st.session_state.data_cache[cache_key]
    auth_headers = get_auth_headers()
    if not auth_headers: st.error("Auth token missing for ranks."); return []
    try:
        response = requests.get(f"{FLASK_API_URL}/get_game_ranks/{game_id}", headers=auth_headers)
        if response.status_code == 401: st.error("Auth failed (ranks)."); st.session_state.jwt_token = None; st.session_state.auth_mode = 'guest'; st.rerun(); return []
        response.raise_for_status(); ranks = response.json().get('ranks', []); st.session_state.data_cache[cache_key] = ranks; return ranks
    except requests.exceptions.RequestException as e: st.error(f"Error fetching ranks for game {game_id}: {e}"); return []
    
def get_game_modes(game_id):
    """Fetches unique game modes for a game (scoped to user) from the backend or cache."""
    if not st.session_state.is_trusted_user or not game_id: return []
    cache_key = f"game_modes_{st.session_state.email}_{game_id}"
    if cache_key in st.session_state.data_cache: 
        return st.session_state.data_cache[cache_key]
    
    auth_headers = get_auth_headers()
    if not auth_headers: st.error("Auth token missing for game modes."); return []
    try:
        response = requests.get(f"{FLASK_API_URL}/get_game_modes/{game_id}", headers=auth_headers)
        if response.status_code == 401: st.error("Auth failed (game modes)."); st.session_state.jwt_token = None; st.session_state.auth_mode = 'guest'; st.rerun(); return []
        response.raise_for_status()
        modes = response.json().get('game_modes', [])
        st.session_state.data_cache[cache_key] = modes
        return modes
    except requests.exceptions.RequestException as e: 
        st.error(f"Error fetching game modes for game {game_id}: {e}"); return []

def get_game_stat_types(game_id):
    """Fetches unique stat types for a game (scoped to user) from the backend or cache."""
    if not st.session_state.is_trusted_user or not game_id: return []
    cache_key = f"game_stat_types_{st.session_state.email}_{game_id}"
    if cache_key in st.session_state.data_cache: 
        return st.session_state.data_cache[cache_key]
    
    auth_headers = get_auth_headers()
    if not auth_headers: st.error("Auth token missing for stat types."); return []
    try:
        response = requests.get(f"{FLASK_API_URL}/get_game_stat_types/{game_id}", headers=auth_headers)
        if response.status_code == 401: st.error("Auth failed (stat types)."); st.session_state.jwt_token = None; st.session_state.auth_mode = 'guest'; st.rerun(); return []
        response.raise_for_status()
        stat_types = response.json().get('stat_types', [])
        st.session_state.data_cache[cache_key] = stat_types
        return stat_types
    except requests.exceptions.RequestException as e: 
        st.error(f"Error fetching stat types for game {game_id}: {e}"); return []

def get_game_franchises():
    """Fetches all unique game franchises associated with the logged-in user."""
    if not st.session_state.auth_mode == 'logged_in': return []
    cache_key = f"game_franchises_{st.session_state.email}"
    if cache_key in st.session_state.data_cache: return st.session_state.data_cache[cache_key]
    
    auth_headers = get_auth_headers()
    if not auth_headers: st.error("Auth token missing for game franchises."); return []
    try:
        response = requests.get(f"{FLASK_API_URL}/get_game_franchises", headers=auth_headers)
        if response.status_code == 401: st.error("Auth failed (game franchises)."); st.session_state.jwt_token = None; st.session_state.auth_mode = 'guest'; st.rerun(); return []
        response.raise_for_status()
        franchises = response.json().get('game_franchises', [])
        st.session_state.data_cache[cache_key] = franchises
        return franchises
    except requests.exceptions.RequestException as e: 
        st.error(f"Error fetching game franchises: {e}"); return []

def get_game_installments(franchise_name):
    """Fetches game installments (id, name) for a specific franchise, scoped to the user."""
    if not st.session_state.auth_mode == 'logged_in': return []
    # Don't cache this as it's dynamic based on selection
    
    auth_headers = get_auth_headers()
    if not auth_headers: st.error("Auth token missing for game installments."); return []
    try:
        # URL encode the franchise name in case it has spaces or special chars
        encoded_franchise_name = requests.utils.quote(franchise_name)
        response = requests.get(f"{FLASK_API_URL}/get_game_installments/{encoded_franchise_name}", headers=auth_headers)
        if response.status_code == 401: st.error("Auth failed (game installments)."); st.session_state.jwt_token = None; st.session_state.auth_mode = 'guest'; st.rerun(); return []
        response.raise_for_status()
        games = response.json().get('game_installments', [])
        return games
    except requests.exceptions.RequestException as e: 
        st.error(f"Error fetching game installments for {franchise_name}: {e}"); return []
        
def set_live_dashboard_state(player_id, game_id):
    """Tells the backend which player/game is currently active."""
    if not st.session_state.is_trusted_user: return
    
    auth_headers = get_auth_headers()
    if not auth_headers:
        st.error("Auth token missing, cannot set live state.")
        return
        
    payload = {"player_id": player_id, "game_id": game_id}
    
    try:
        response = requests.post(f"{FLASK_API_URL}/set_live_state", json=payload, headers=auth_headers)
        response.raise_for_status()
        print(f"Successfully set live state: Player {player_id}, Game {game_id}")
    except requests.exceptions.RequestException as e:
        st.error(f"Could not set live dashboard state: {e}")
        
# --- Database Read Functions (Direct Connection - TRUSTED USERS ONLY) ---
def get_db_conn_read_only():
    if not st.session_state.is_trusted_user:
        return None
    try:
        engine = create_engine(
            f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_URL}:5439/{DB_NAME}",
            connect_args={"connect_timeout": 5}
        )
        return engine.connect()
    except Exception as e:
        print(f"SQLAlchemy connection error: {e}")
        return None

def get_recent_stats_for_display(limit=50):
    if not st.session_state.is_trusted_user:
        return pd.DataFrame()
    conn = get_db_conn_read_only()
    if not conn: return pd.DataFrame()
    try:
        query = """
            SELECT
                t1.stat_id, t2.game_name, t3.player_name, t1.stat_type, t1.stat_value, t1.played_at,
                t1.ranked, t1.pre_match_rank_value, t1.post_match_rank_value, t1.game_mode, t1.game_level, t1.win
            FROM fact.fact_game_stats t1
            JOIN dim.dim_games t2 ON t1.game_id = t2.game_id
            JOIN dim.dim_players t3 ON t1.player_id = t3.player_id
            WHERE t3.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = %s)
            ORDER BY t1.played_at DESC LIMIT %s;
        """
        params = (st.session_state.email, limit)
        df = pd.read_sql_query(query, conn, params=params)
        return df
    except Exception as e:
        st.error(f"Error fetching recent stats: {e}")
        return pd.DataFrame()
    finally:
        if conn: conn.close()

# --- UI Action Callbacks ---
def add_stat_input():
    st.session_state.num_stats += 1

def delete_stat_input():
    if st.session_state.num_stats > 1:
        st.session_state.num_stats -= 1
    
def update_genre_state():
    # Callback for the *new game* genre dropdown
    st.session_state.selected_genre = st.session_state.new_game_genre_select # Use the new unique key
    subgenre_options = GENRES.get(st.session_state.selected_genre, ["Select a Subgenre"])
    st.session_state.selected_subgenre = subgenre_options[0]


# --- Guest-specific callback ---
def update_guest_genre_state_callback():
    st.session_state.guest_selected_genre = st.session_state.guest_new_game_genre_select
    sub_opts = GENRES.get(st.session_state.guest_selected_genre, ["Select a Subgenre"])
    st.session_state.guest_selected_subgenre = sub_opts[0]
   
def clear_edit_cache():
    st.session_state.data_cache.pop(f"players_{st.session_state.email}", None)
    st.session_state.data_cache.pop(f"all_games_{st.session_state.email}", None)
    st.session_state.stat_edit_data_loaded = False
    st.session_state.stat_edit_confirmed = False
    st.session_state.player_edit_data_loaded = False
    st.session_state.player_edit_confirmed = False
    st.session_state.game_edit_data_loaded = False
    st.session_state.game_edit_confirmed = False

def clear_delete_cache():
    st.session_state.data_cache.pop(f"players_{st.session_state.email}", None)
    st.session_state.data_cache.pop(f"all_games_{st.session_state.email}", None)
    st.session_state.stat_delete_data_loaded = False
    st.session_state.stat_delete_confirmed = False
    st.session_state.player_delete_data_loaded = False
    st.session_state.player_delete_confirmed = False
    st.session_state.game_delete_data_loaded = False
    st.session_state.game_delete_confirmed = False
    st.session_state.last_deleted_game_id = None