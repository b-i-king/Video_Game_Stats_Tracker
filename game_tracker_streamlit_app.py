import streamlit as st
import requests
from sqlalchemy import create_engine
import pandas as pd
from datetime  import datetime

# Get environment variables
FLASK_API_URL = st.secrets.flask.flask_api_url
DB_URL = st.secrets.redshift.database_url
DB_NAME = st.secrets.redshift.database_name
DB_USER = st.secrets.redshift.database_user 
DB_PASSWORD = st.secrets.redshift.database_password
API_KEY = st.secrets.config.api_key
TRUSTED_EMAILS = st.secrets.config.trusted_emails

# Validate essential secrets
if not API_KEY:
    st.error("API_KEY must be set in Streamlit secrets.")
    st.stop()
if not all([DB_URL, DB_NAME, DB_USER, DB_PASSWORD]):
    st.error("Redshift database connection details (DB_URL, DB_NAME, DB_USER, DB_PASSWORD) must be set in Streamlit secrets.")
    st.stop()
if not TRUSTED_EMAILS:
    st.warning("TRUSTED_EMAILS list is not set or empty in Streamlit secrets. No users will be treated as admin.")
     
st.set_page_config(layout="wide")

# Define the genre and subgenre data
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

# Session state to handle dynamic form inputs and login status
if 'num_stats' not in st.session_state:
    st.session_state.num_stats = 1
if 'player_name' not in st.session_state:
    st.session_state.player_name = None
if 'player_id' not in st.session_state:
    st.session_state.player_id = None
if 'selected_game_for_rank' not in st.session_state:
    st.session_state.selected_game_for_rank = None
if 'selected_genre' not in st.session_state:
    st.session_state.selected_genre = "Select a Genre"
if 'selected_subgenre' not in st.session_state:
    st.session_state.selected_subgenre = "Select a Subgenre"
if 'is_trusted_user' not in st.session_state:
    st.session_state.is_trusted_user = False
if 'email' not in st.session_state:
    st.session_state.email = None
if 'auth_mode' not in st.session_state:
    st.session_state.auth_mode = 'guest' # 'guest', 'prompt_login', 'logged_in'
if 'data_cache' not in st.session_state:
    st.session_state.data_cache = {}
if 'jwt_token' not in st.session_state:
    st.session_state.jwt_token = None
if 'last_deleted_game_id' not in st.session_state:
    st.session_state.last_deleted_game_id = None
    
# Set state variables for Edit/Delete tabs
if 'player_edit_data_loaded' not in st.session_state:
    st.session_state.player_edit_data_loaded =  False
if 'game_edit_data_loaded' not in st.session_state:
    st.session_state.game_edit_data_loaded = False
if 'stat_edit_data_loaded' not in st.session_state:
    st.session_state.stat_edit_data_loaded = False
if 'player_delete_data_loaded' not in st.session_state: 
    st.session_state.player_delete_data_loaded = False
if 'game_delete_data_loaded' not in st.session_state:
    st.session_state.game_delete_data_loaded = False
if 'stat_delete_data_loaded' not in st.session_state:
    st.session_state.stat_delete_data_loaded = False

if 'player_edit_confirmed' not in st.session_state:
    st.session_state.player_edit_confirmed = False
if 'game_edit_confirmed' not in st.session_state:
    st.session_state.game_edit_confirmed = False
if 'stat_edit_confirmed' not in st.session_state:
    st.session_state.stat_edit_confirmed = False
if 'player_delete_confirmed' not in st.session_state:
    st.session_state.player_delete_confirmed = False
if 'game_delete_confirmed' not in st.session_state:
    st.session_state.game_delete_confirmed = False
if 'stat_delete_confirmed' not in st.session_state:
    st.session_state.stat_delete_confirmed = False

if 'recent_players_df' not in st.session_state:
    st.session_state.recent_players_df = pd.DataFrame()
if 'recent_games_df' not in st.session_state:
    st.session_state.recent_games_df = pd.DataFrame()
if 'recent_stats_df' not in st.session_state:
    st.session_state.recent_stats_df = pd.DataFrame()

# Rank data session state
if 'is_ranked' not in st.session_state:
    st.session_state.is_ranked = False
if 'pre_match_rank_value' not in st.session_state:
    st.session_state.pre_match_rank_value = "Unranked"
if 'post_match_rank_value' not in st.session_state:
    st.session_state.post_match_rank_value = "Unranked"

# --- Authentication Logic ---
def attempt_flask_login(user_email):
    """Requests a JWT from the Flask backend and updates session state based on backend response."""
    try:
        print(f"Attempting Flask login for trusted user: {user_email}...") # Debug
        response = requests.post(
            f"{FLASK_API_URL}/login",
            headers={"X-API-KEY": API_KEY, "Content-Type": "application/json"},
            json={"email": user_email}
        )
        response.raise_for_status()
        token = response.json().get('token')
        is_trusted_from_backend = response.json().get('is_trusted', False)

        if token and is_trusted_from_backend: # Only store token if user is trusted
            print(f"Flask login successful. JWT received. Backend confirmed Trusted: {is_trusted_from_backend}") # Debug
            st.session_state.jwt_token = token
            st.session_state.is_trusted_user = True
            st.session_state.auth_mode = 'logged_in'
            st.session_state.email = user_email
            return True
        elif is_trusted_from_backend is False:
            # User exists in backend but is not trusted - treat as guest
            print(f"Flask login: User {user_email} exists but is not trusted.") # Debug
            st.session_state.auth_mode = 'guest' # Revert to guest mode
            st.session_state.is_trusted_user = False
            st.session_state.jwt_token = None
            st.session_state.email = user_email # Keep email for sidebar info
            return False # Indicate non-admin login
        else: # Catch case where token might be missing but trusted somehow (shouldn't happen)
            print("Flask login failed: No token received or backend trust issue.") # Debug
            st.error("Authentication with backend failed.")
            st.session_state.auth_mode = 'login_failed'
            return False
    except requests.exceptions.RequestException as e:
        print(f"Flask login failed: Request Exception: {e}") # Debug
        error_detail = str(e)
        if 'response' in locals() and response is not None:
             try: error_detail = response.json().get("error", response.text)
             except ValueError: error_detail = response.text
        st.error(f"Failed to authenticate with backend: {error_detail}")
        st.session_state.auth_mode = 'login_failed'
        return False

def register_guest_user(user_email):
    """Registers a non-trusted user in the backend. Returns True on success, False on failure."""
    try:
        print(f"Registering guest user {user_email} in backend...") # Debug
        reg_response = requests.post(
            f"{FLASK_API_URL}/add_user",
            headers={"X-API-KEY": API_KEY, "Content-Type": "application/json"},
            json={"email": user_email}
        )
        reg_response.raise_for_status()
        print(f"Guest registration check completed (Status: {reg_response.status_code})") # Debug
        # Keep frontend state as guest even after registration
        st.session_state.is_trusted_user = False
        st.session_state.auth_mode = 'guest' # Stay in guest mode UI
        st.session_state.email = user_email # Keep email for sidebar info if needed
        st.session_state.jwt_token = None
        return True
    except requests.exceptions.RequestException as e:
         print(f"Warning: Failed to ensure guest user registration: {e}")
         st.warning(f"Could not register guest user with backend: {e}")
         st.session_state.auth_mode = 'login_failed' # Treat registration failure as login failure
         return False

# --- State Management at the Start of Each Rerun ---

# 1. Check if already logged in via Streamlit Cloud's st.user
current_user_email = getattr(st.user, "email", None)

# 2. Handle the state after Google Login promptdeleting individual stat entries (e.g., a single matdeleting individual stat entries (e.g., a single match).d
if st.session_state.auth_mode == 'guest' and current_user_email:
    # Auto-detected user logged into Streamlit Cloud, process them
    print(f"Detected Streamlit Cloud user {current_user_email} while in guest mode.") # Debug
    if current_user_email in TRUSTED_EMAILS:
        print("User is in trusted list, attempting Flask login...") # Debug
        # attempt_flask_login updates state internally
        attempt_flask_login(current_user_email)
    else:
        print("User is NOT in trusted list, registering as guest...") # Debug
        # register_guest_user keeps state as guest
        register_guest_user(current_user_email)
    # Rerun needed to apply the state changes from attempt_flask_login or register_guest_user
    st.rerun()

elif st.session_state.auth_mode == 'prompt_login':
    # This state means the 'Login with Google' button was clicked
    # Now call st.login() to show the Google Auth UI
    st.login("google")
    # Streamlit handles the redirect. The logic above will catch the user
    # when they return and st.user is populated.
    st.sidebar.warning("Waiting for Google login completion...")

# --- Sidebar Auth UI ---
st.sidebar.title("Authentication")

# Ddeleting individual stat entries (e.g., adeleting individual stat entries (e.g., a single match).
if st.session_state.auth_mode == 'guest' or st.session_state.auth_mode == 'login_failed':
    st.sidebar.info("You are currently in Guest Mode.")
    if st.session_state.auth_mode == 'login_failed':
        st.sidebar.error("Previous login/registration attempt failed.")

    col_login, col_guest = st.sidebar.columns(2)
    with col_login:
        if st.button("Login with Google"):
            st.session_state.auth_mode = 'prompt_login'
            st.rerun()
    with col_guest:
        st.button("Continue as Guest", disabled=(st.session_state.auth_mode == 'guest'))

elif st.session_state.auth_mode == 'logged_in':
    # This mode now implies either trusted deleting individual stat entries (e.g., a single match).deleting individual stat entries (e.g., a single match).deleting individual stat entries (e.g., a single match).user or registered guest (but UI treats registered guest like anonymous guest)
    if st.session_state.is_trusted_user:
        st.sidebar.success(f"Logged in as Admin: {st.session_state.email}")
    else:
        # Show generic guest message even if registered, as UI is the same
        st.sidebar.info(f"Logged in as Guest: {st.session_state.email}")

    if st.sidebar.button("Logout"):
        # Reset all relevant session state variables
        st.session_state.email = None
        st.session_state.is_trusted_user = False
        # st.session_state.is_registered_guest = False # No longer needed
        st.session_state.jwt_token = None
        st.session_state.auth_mode = 'guest'
        st.session_state.player_name = None # Reset player selection
        st.session_state.data_cache = {} # Clear cache
        st.session_state.edit_confirmed = False
        st.session_state.delete_confirmed = False
        st.session_state.edit_data_loaded = False
        st.session_state.delete_data_loaded = False
        print("Logout successful, resetting state.") # Debug
        st.rerun()

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

def get_player_games(player_id):
    """Fetches games for a specific player (owned by user)."""
    if not st.session_state.is_trusted_user or not player_id: return []
    cache_key = f"player_games_{st.session_state.email}_{player_id}"
    if cache_key in st.session_state.data_cache: return st.session_state.data_cache[cache_key]
    auth_headers = get_auth_headers()
    if not auth_headers: st.error("Auth token missing for games."); return []
    try:
        response = requests.get(f"{FLASK_API_URL}/get_player_games/{player_id}", headers=auth_headers)
        if response.status_code == 401: st.error("Auth failed (games)."); st.session_state.jwt_token = None; st.session_state.auth_mode = 'guest'; st.rerun(); return []
        response.raise_for_status(); games = response.json().get('games', []); st.session_state.data_cache[cache_key] = games; return games
    except requests.exceptions.RequestException as e: st.error(f"Error fetching games for player {player_id}: {e}"); return []

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

# --- UI Rendering ---
st.markdown("<h1 style='text-align: center; color: #c8ac44'>🎮 Video Game Stats Entry</h1>", unsafe_allow_html=True)

# --- Player Selection (Trusted Users Only) ---
if st.session_state.is_trusted_user:
    st.subheader("Select or add a player associated with your account.", divider="grey")

    players_list_data = get_all_players() # Safe to call now
    player_name_to_id = {p["player_name"]: p["player_id"] for p in players_list_data}
    player_options = ["- Select player -", "Add a new player"] + list(player_name_to_id.keys())
    
    if st.session_state.player_name not in player_name_to_id:
        st.session_state.player_name = None
        st.session_state.player_id = None


    with st.form(key='player_selection_form'):
        current_player_index = (
            player_options.index(st.session_state.player_name)
            if st.session_state.player_name in player_options
            else 0
        )
        selected_player_name = st.selectbox("Player Name", player_options, help="Select past player profile or create new player profile", index=current_player_index)
        new_player_name_input = ""
        if selected_player_name == "Add a new player":
            new_player_name_input = st.text_input("New Player Name", help="Enter name for new player profile.")

        player_select_submitted = st.form_submit_button("Proceed")

        if player_select_submitted:
            player_changed = False
            new_selection = None
            if selected_player_name == "- Select player -": st.warning("Please select or add a player.")
            elif selected_player_name == "Add a new player":
                if not new_player_name_input.strip(): st.warning("New player name cannot be empty.")
                else: new_selection = new_player_name_input.strip()
            else: new_selection = selected_player_name

            if new_selection and st.session_state.player_name != new_selection:
                st.session_state.player_name = new_selection
                st.session_state.player_id = player_name_to_id.get(new_selection) 
                st.success(f"Player set to '{st.session_state.player_name}'.")
                keys_to_remove = [k for k in st.session_state.data_cache if k.startswith(f"player_games_{st.session_state.email}") or k.startswith(f"game_ranks_{st.session_state.email}")]
                for k in keys_to_remove: st.session_state.data_cache.pop(k, None)
                st.session_state.selected_game_for_rank = None
                st.rerun()
            elif new_selection and st.session_state.player_name == new_selection:
                 st.info(f"Player '{st.session_state.player_name}' already selected.")
                 
# --- Guest Mode UI ---
elif st.session_state.auth_mode == 'guest' or (st.session_state.auth_mode == 'logged_in' and not st.session_state.is_trusted_user):
    st.info("Log in via the sidebar using a trusted email to select a player and manage stats.")
    # (The rest of the guest UI from your file)
    with st.container():
        col1, col2 = st.columns([2, 1],border=True, vertical_alignment="center")
    with col1:
        st.selectbox("Select a Game (Guest Mode)", ["Add a New Game"], key="guest_game_select", disabled=True)
    with col2:
        st.button("Add Another Stat", on_click=add_stat_input, use_container_width=True)
        st.button("Delete Last Stat", on_click=delete_stat_input, use_container_width=True)
        
    st.markdown("---")
    st.subheader("New Game Details (Guest Mode)")
    st.text_input("New Game Name *", help="The name of the new game", key="guest_new_game")
    st.selectbox("Game Genre *", list(GENRES.keys()), key="guest_genre_select")
    st.selectbox("Game Subgenre *", ["Select a Subgenre"], key="guest_subgenre_select")
    st.text_input("Game Series (Optional)", help="The series of the game", key="guest_game_series")
    st.markdown("---")
    
    # --- Rank Selection Section (outside the form for reactivity) ---
    st.markdown("### Rank Information")

    is_ranked_guest = st.checkbox("Ranked?")
    if is_ranked_guest:
        st.text_input("Pre-match Rank (Guest Mode)", help="This will not be saved.")
        st.text_input("Post-match Rank (Guest Mode)", help="This will not be saved.")
     
    with st.form(key='guest_game_stats_form'):
        st.markdown(f"**Entering stats for:** `Guest Player`")
        st.text_input("Game Mode (Optional)", help="e.g., 'Team Deathmatch', 'Battle Royale'")
        st.number_input("Game Level/Wave (Optional)", min_value=0, step=1, help="e.g., 'Wave 10'")
        st.selectbox("Win/Loss", [None, 'Win', 'Loss'], help="Select Win or Lose. Leave 'None' if N/A", format_func=lambda x: 'Select an option' if x is None else x)
        
        st.subheader("Stats")
        for i in range(st.session_state.num_stats):
            col1, col2 = st.columns(2)
            with col1:
                st.text_input(f"Stat Type {i+1}", key=f"stat_type_guest_{i}")
            with col2:
                st.number_input(f"Stat Value {i+1}", min_value=0, step=1, key=f"stat_value_guest_{i}")
        st.form_submit_button("Submit Form (Guest Mode)", help="This will not save data.")


elif st.session_state.auth_mode == 'prompt_login':
    st.info("Complete Google Login using the popup or sidebar.")

# --- Main Content Area (Tabs for Trusted, Guest UI for others) ---
if st.session_state.player_name and st.session_state.is_trusted_user:
    player_id = st.session_state.player_id
    
    tab_list = ["Enter Stats", "Edit", "Delete"]
    tabs = st.tabs(tab_list)

    # --- Enter Stats Tab ---
    with tabs[0]:
        with st.container(border=True):
            col_game, col_add_stat, col_del_stat = st.columns([3, 1, 1], vertical_alignment="bottom")
            with col_game:
                # Get games based on player_id if it exists
                player_games = get_player_games(player_id) if player_id else [] # player_games is list of dicts
                game_options = ["Add a New Game"] + [game['game_name'] for game in player_games] # Use list of names

                # If selected_game_for_rank missing or no longer valid for the current player's games, default to "Add a New Game"
                if ('selected_game_for_rank' not in st.session_state) or (st.session_state.selected_game_for_rank not in game_options):
                    st.session_state.selected_game_for_rank = "Add a New Game"

                # Use the validated session-state value as the selectbox's default
                current_game_selection = st.session_state.get('selected_game_for_rank')
                default_game_index = 0
                if current_game_selection and current_game_selection in game_options:
                    default_game_index = game_options.index(current_game_selection)
                elif not current_game_selection:
                     st.session_state.selected_game_for_rank = game_options[0]

                st.selectbox(
                     "Select or Add Game", game_options, help="Select past game or create a new game", key="game_select_key_outside",
                     index=default_game_index,
                     on_change=lambda: st.session_state.update(selected_game_for_rank=st.session_state.game_select_key_outside)
                )
            with col_add_stat: st.button("➕ Stat Row", on_click=add_stat_input, use_container_width=True)
            with col_del_stat: st.button("➖ Stat Row", on_click=delete_stat_input, use_container_width=True)

        game_name_from_state = st.session_state.selected_game_for_rank
        is_new_game_mode = (game_name_from_state == "Add a New Game")
        
        selected_game_id = None
        if not is_new_game_mode and player_id: # Only search if it's an existing game
             for game in player_games: # Use the fetched list of dicts
                 if game['game_name'] == game_name_from_state:
                     selected_game_id = game['game_id']
                     break
        
        # --- Genre/Subgenre (Conditional, outside form) ---
        new_game_name_input, new_game_series_input = "", ""
        new_game_genre_selected, new_game_subgenre_selected = st.session_state.selected_genre, st.session_state.selected_subgenre

        if is_new_game_mode:
            st.markdown("---"); st.subheader("New Game Details")
            new_game_name_input = st.text_input("New Game Name *", help="The name of the new game", key="new_game_name_input_outside")
            # Use a unique key for the genre selectbox
            new_game_genre_selected = st.selectbox( "Game Genre *", list(GENRES.keys()), help="Select the genre of the game", key="new_game_genre_select",
                index=list(GENRES.keys()).index(st.session_state.selected_genre), on_change=update_genre_state )
            
            subgenre_options = GENRES.get(st.session_state.selected_genre, ["Select a Subgenre"])
            current_subgenre = st.session_state.selected_subgenre
            if current_subgenre not in subgenre_options: current_subgenre = subgenre_options[0]
            # Use a unique key for the subgenre selectbox
            new_game_subgenre_selected = st.selectbox( "Game Subgenre *", subgenre_options, help="Select the subgenre of the game", key="new_game_subgenre_select",
                index=subgenre_options.index(current_subgenre) )
            new_game_series_input = st.text_input("Game Series (Optional)", key="new_game_series_input_outside")
            st.markdown("---")
        
        # Determine final game details based on mode
        if is_new_game_mode:
            final_game_name = new_game_name_input
            final_game_series = new_game_series_input
            final_game_genre = st.session_state.selected_genre # Read from state set by callback
            final_game_subgenre = new_game_subgenre_selected # Read from the widget
        else:
            final_game_name = game_name_from_state
            final_game_series, final_game_genre, final_game_subgenre = None, None, None
        
        # --- Stat Type Guidance ---
        if not is_new_game_mode and selected_game_id:
            stat_types_list = get_game_stat_types(selected_game_id)
            if stat_types_list:
                st.info(f"**Tip:** For '{game_name_from_state}', you previously used these stat types: \n- " + "\n- ".join(stat_types_list))
    
        # --- Rank Selection Section (outside the form for reactivity) ---
        st.markdown("### Rank Information") 

        # Keep checkbox synced to session_state
        st.checkbox("Ranked?", help="Is this game mode a ranked match?",  key="is_ranked")

        # Dynamically render rank inputs when ranked
        if st.session_state.is_ranked:
            st.markdown("**Enter Rank Details**")
            pre_match_rank_final = "Unranked"
            post_match_rank_final = "Unranked"
            
            if not is_new_game_mode and selected_game_id:
                ranks_list = get_game_ranks(selected_game_id) # Fetch ranks by ID
                if not ranks_list:
                    st.warning("No ranks found for this game. Please enter ranks manually.")
                    ranks_list = ["Unranked"]
                rank_options = list(set(ranks_list)) + ["(Enter New Rank)"] # Unique ranks
                
                 # --- Pre-match Rank ---
                pre_rank_select = st.selectbox("Pre-match Rank (Select)", rank_options, index=0, key="pre_rank_select", help="Select pre-match rank")
                pre_match_rank_text = ""
                if pre_rank_select == "(Enter New Rank)":
                    pre_match_rank_text = st.text_input("New Pre-match Rank", value="", help="Type the new rank.")
                pre_match_rank_final = pre_match_rank_text.strip() if pre_match_rank_text.strip() else pre_rank_select

                # --- Post-match Rank ---
                post_rank_select = st.selectbox("Post-match Rank (Select)", rank_options, index=0, key="post_rank_select", help="Select post-match rank")
                post_match_rank_text = ""
                if post_rank_select == "(Enter New Rank)":
                    post_match_rank_text = st.text_input("New Post-match Rank", value="", help="Type the new rank.")
                post_match_rank_final = post_match_rank_text.strip() if post_match_rank_text.strip() else post_rank_select

            else: # New game mode
                 pre_match_rank_final = st.text_input("Pre-match Rank", value="Unranked", key="pre_rank_text_new" , help="Enter pre-match rank")
                 post_match_rank_final = st.text_input("Post-match Rank", value="Unranked", key="post_rank_text_new" , help="Enter post-match rank")
            
            # Store the final values in session_state so the form can read them
            st.session_state.pre_match_rank_value = pre_match_rank_final
            st.session_state.post_match_rank_value = post_match_rank_final
        

        with st.form(key='game_stats_form'):
            st.markdown(f"**Entering stats for:** `{st.session_state.player_name}` | **Game:** `{game_name_from_state if not is_new_game_mode else '(New Game)'}`")
            
            # --- Hybrid Game Mode Input ---
            game_mode_select_options = ["Main"]
            if not is_new_game_mode and selected_game_id:
                game_mode_list = get_game_modes(selected_game_id)
                if game_mode_list:
                    game_mode_select_options = list(set(game_mode_list))
            
            game_mode_select = st.selectbox("Game Mode *", game_mode_select_options, index=0, key="game_mode_select_inside", help="Select existing mode.")
            new_game_mode_text = st.text_input("Game Mode (New/Override)", value="", help="Leave blank to use selection. Type a new mode here.")
            
            # Prioritize text input if filled, otherwise use selection
            final_game_mode = new_game_mode_text.strip() if new_game_mode_text.strip() else game_mode_select
         
            # game_mode = st.text_input("Game Mode *", value="Main", help="e.g., 'Team Deathmatch', 'Battle Royale'")
            game_level = st.number_input("Game Level/Wave", help="e.g., 'Wave 10', 'Episode 1', 'Mission 3'", value=None, min_value=0, step=1)
            win_option = st.selectbox("Win/Loss", [None, 'Win', 'Loss'], help="Select Win or Lose. Leave 'None' if N/A", index=0)
            win_value = 1 if win_option == 'Win' else 0 if win_option == 'Loss' else None

            st.subheader("Stats")
            stats_list = []
            for i in range(st.session_state.num_stats):
                st.markdown(f"**Stat Set {i+1}**"); cols = st.columns(2)
                stat_type = cols[0].text_input(f"Stat Type", help="e.g., 'Points', 'Eliminations'", key=f"stat_type_{i}")
                stat_value = cols[1].number_input(f"Stat Value", help="Numeric value of specific statistics", value=0, min_value=0, step=1, key=f"stat_value_{i}")
                
                is_ranked_from_state = st.session_state.get('is_ranked', False)
                pre_rank_from_state = st.session_state.get('pre_match_rank_value') if is_ranked_from_state else None
                post_rank_from_state = st.session_state.get('post_match_rank_value') if is_ranked_from_state else None
                
                if stat_type and stat_value is not None and stat_value >= 0:
                    stats_list.append({
                        "stat_type": stat_type, "stat_value": int(stat_value),
                        "game_mode": final_game_mode or "Main", 
                        "game_level": int(game_level) if game_level and game_level > 0 else None,
                        "win": win_value, 
                        "ranked": 1 if is_ranked_from_state else 0,
                        "pre_match_rank_value": pre_rank_from_state,
                        "post_match_rank_value": post_rank_from_state
                    })
            
            submitted = st.form_submit_button("Submit Stats")
            if submitted:
                valid = False
                if is_new_game_mode:
                    if final_game_name and final_game_genre != "Select a Genre" and final_game_subgenre != "Select a Subgenre" and stats_list: 
                        valid = True
                    else: st.warning("Fill New Game Name, Genre, Subgenre, & ≥1 Stat.")
                else:
                    if final_game_name and final_game_name != "Add a New Game" and st.session_state.player_name and stats_list: 
                        valid = True
                    else: st.warning("Ensure game selected & ≥1 Stat entered.")
                
                if valid:
                    # Payload is built here, reading from state
                    payload = {"game_name": final_game_name, "game_series": final_game_series,
                               "game_genre": final_game_genre, "game_subgenre": final_game_subgenre,
                               "player_name": st.session_state.player_name, 
                               "stats": stats_list # stats_list now contains the rank data
                               }
                    auth_headers = get_auth_headers()
                    if auth_headers:
                        try:
                            response = requests.post(f"{FLASK_API_URL}/add_stats", json=payload, headers=auth_headers)
                            response.raise_for_status(); st.success("Stats submitted!"); st.session_state.num_stats = 1; st.session_state.data_cache.clear(); st.session_state.selected_genre = "Select a Genre"; st.session_state.selected_subgenre = "Select a Subgenre"; st.rerun()
                        except requests.exceptions.RequestException as e:
                            st.error(f"Submit error: {e}")
                            if 'response' in locals() and response is not None:
                                 try: error_detail = response.json().get("error", response.text)
                                 except ValueError: error_detail = response.text
                                 if response.status_code == 401: st.error("Auth error."); st.session_state.jwt_token = None; st.session_state.auth_mode = 'guest'; st.rerun()
                                 elif response.status_code == 403: st.error("Permission denied.")
                                 else: st.error(f"Backend error: {error_detail}")

    # --- Edit Tab ---
    if st.session_state.is_trusted_user:
        with tabs[1]:
            st.subheader("Edit Data")
            edit_tabs = st.tabs(["Edit Player", "Edit Game", "Edit Stats"])

            # --- Edit Player ---
            with edit_tabs[0]:
                st.markdown("Select a player profile to rename.")
                if st.button("Load Players to Edit", key="load_edit_player_button"):
                    st.session_state.recent_players_df = pd.DataFrame(get_all_players())
                    st.session_state.player_edit_data_loaded = True
                    st.session_state.player_edit_confirmed = False
                    st.rerun()

                if st.session_state.player_edit_data_loaded:
                    players_df = st.session_state.recent_players_df
                    if not players_df.empty:
                        player_name_to_id = {p["player_name"]: p["player_id"] for index, p in players_df.iterrows()}
                        player_options = ["- Select player -"] + list(player_name_to_id.keys())
                        selected_player_name_to_edit = st.selectbox("Select Player to Edit", player_options, key="edit_player_select", index=0)
                        
                        if selected_player_name_to_edit and selected_player_name_to_edit != "- Select player -":
                            selected_player_id_to_edit = player_name_to_id[selected_player_name_to_edit]
                            
                            if not st.session_state.player_edit_confirmed:
                                if st.button("Confirm Edit Player", key="confirm_edit_player_button"):
                                    st.session_state.player_edit_confirmed = True; st.rerun()

                            if st.session_state.player_edit_confirmed:
                                st.info(f"You are editing: **{selected_player_name_to_edit}** (ID: {selected_player_id_to_edit})")
                                with st.form(key=f"edit_player_form_{selected_player_id_to_edit}"):
                                    new_player_name = st.text_input("New Player Name", value=selected_player_name_to_edit)
                                    submitted_edit_player = st.form_submit_button("Update Player Name")
                                    if submitted_edit_player:
                                        if new_player_name and new_player_name != selected_player_name_to_edit:
                                            auth_headers = get_auth_headers()
                                            if auth_headers:
                                                try:
                                                    payload = {"player_name": new_player_name}
                                                    response = requests.put(f"{FLASK_API_URL}/update_player/{selected_player_id_to_edit}", json=payload, headers=auth_headers)
                                                    response.raise_for_status()
                                                    st.success(f"Player '{selected_player_name_to_edit}' renamed to '{new_player_name}'!")
                                                    clear_edit_cache(); st.rerun()
                                                except requests.exceptions.RequestException as e:
                                                    st.error(f"Error updating player: {e}")
                                                    # (Add full error handling)
                                        else:
                                            st.warning("Please enter a new name.")
                    else: st.info("No players found for your account.")

            # --- Edit Game ---
            with edit_tabs[1]:
                st.markdown("Select a game to edit its details.")
                if st.button("Load Games to Edit", key="load_edit_game_button"):
                    st.session_state.recent_games_df = pd.DataFrame(get_all_games())
                    st.session_state.game_edit_data_loaded = True
                    st.session_state.game_edit_confirmed = False
                    st.rerun()

                if st.session_state.game_edit_data_loaded:
                    games_df = st.session_state.recent_games_df
                    if not games_df.empty:
                        game_name_to_id = {g["game_name"]: g["game_id"] for index, g in games_df.iterrows()}
                        game_options = ["- Select game -"] + list(game_name_to_id.keys())
                        selected_game_name_to_edit = st.selectbox("Select Game to Edit", game_options, key="edit_game_select", index=0)

                        if selected_game_name_to_edit and selected_game_name_to_edit != "- Select game -":
                            selected_game_id_to_edit = game_name_to_id[selected_game_name_to_edit]
                            
                            if not st.session_state.game_edit_confirmed:
                                if st.button("Confirm Edit Game", key="confirm_edit_game_button"):
                                    st.session_state.game_edit_confirmed = True; st.rerun()

                            if st.session_state.game_edit_confirmed:
                                game_details = get_game_details(selected_game_id_to_edit)
                                if game_details:
                                    with st.form(key=f"edit_game_form_{selected_game_id_to_edit}"):
                                        st.info(f"You are editing: **{game_details['game_name']}** (ID: {selected_game_id_to_edit})")
                                        new_game_name = st.text_input("Game Name", value=game_details.get("game_name", ""))
                                        new_game_series = st.text_input("Game Series", value=game_details.get("game_series", "") or "")
                                        
                                        current_genre = game_details.get("game_genre", "Select a Genre")
                                        if current_genre not in GENRES: current_genre = "Select a Genre"
                                        edit_game_genre = st.selectbox("Game Genre *", list(GENRES.keys()), 
                                                                       key="edit_game_genre_select",
                                                                       index=list(GENRES.keys()).index(current_genre))
                                        
                                        edit_subgenre_options = GENRES.get(edit_game_genre, ["Select a Subgenre"])
                                        current_subgenre = game_details.get("game_subgenre", "Select a Subgenre")
                                        if current_subgenre not in edit_subgenre_options: current_subgenre = edit_subgenre_options[0]
                                        edit_game_subgenre = st.selectbox("Game Subgenre *", edit_subgenre_options, 
                                                                          key="edit_game_subgenre_select",
                                                                          index=edit_subgenre_options.index(current_subgenre))

                                        submitted_edit_game = st.form_submit_button("Update Game Details")
                                        if submitted_edit_game:
                                            if new_game_name and edit_game_genre != "Select a Genre" and edit_game_subgenre != "Select a Subgenre":
                                                payload = {
                                                    "game_name": new_game_name, "game_series": new_game_series,
                                                    "game_genre": edit_game_genre, "game_subgenre": edit_game_subgenre
                                                }
                                                auth_headers = get_auth_headers()
                                                if auth_headers:
                                                    try:
                                                        response = requests.put(f"{FLASK_API_URL}/update_game/{selected_game_id_to_edit}", json=payload, headers=auth_headers)
                                                        response.raise_for_status()
                                                        st.success(f"Game '{selected_game_name_to_edit}' updated!")
                                                        clear_edit_cache(); st.rerun()
                                                    except requests.exceptions.RequestException as e:
                                                        st.error(f"Error updating game: {e}")
                                                        if 'response' in locals() and response is not None and response.status_code == 409:
                                                            st.error(f"Update failed: {response.json().get('error')}")
                                            else:
                                                st.warning("Game Name, Genre, and Subgenre are required.")
                                else:
                                    st.error("Could not load game details to edit.")
                    else: st.info("No games found to edit. Add stats for a game first.")

            # --- Edit Stats ---
            with edit_tabs[2]:
                st.markdown("This editing individual stat entries (e.g., a single match).")
                if st.button("Load Data for Editing", key="load_edit_data_button_stats"):
                    st.session_state.recent_stats_df = get_recent_stats_for_display()
                    st.session_state.stat_edit_data_loaded = True; st.session_state.stat_edit_confirmed = False; st.rerun()
                
                if st.session_state.stat_edit_data_loaded:
                    recent_stats_df_edit = st.session_state.recent_stats_df
                    if not recent_stats_df_edit.empty:
                        def format_edit_text(row):
                            text = f"({row['stat_id']}) {row['game_name']} {row['stat_type']} {row['stat_value']} by {row['player_name']} @ {row['played_at'].strftime('%y-%m-%d %H:%M')}"
                            if row['ranked'] == 1: text += f" (R:{row.get('pre_match_rank_value','?')}-{row.get('post_match_rank_value','?')})"
                            return text
                        recent_stats_df_edit['display_text'] = recent_stats_df_edit.apply(format_edit_text, axis=1)
                        selected_entry_edit_text = st.selectbox("Select entry to edit:", recent_stats_df_edit['display_text'], key="edit_select_stat", index=None)
                        
                        if selected_entry_edit_text:
                            selected_row = recent_stats_df_edit[recent_stats_df_edit['display_text'] == selected_entry_edit_text].iloc[0]
                            stat_id_to_edit = int(selected_row['stat_id'])
                            if not st.session_state.stat_edit_confirmed:
                                if st.button("Confirm Edit Selection", key="confirm_edit_button_stat"): st.session_state.stat_edit_confirmed = True; st.rerun()
                            if st.session_state.stat_edit_confirmed:
                                st.info(f"Editing: {selected_entry_edit_text}")
                                with st.form(key=f'edit_form_{stat_id_to_edit}'):
                                    new_stat_type = st.text_input("Stat Type", value=selected_row.get('stat_type', ''))
                                    new_stat_value = st.number_input("Stat Value", value=int(selected_row.get('stat_value', 0)), min_value=0, step=1)
                                    new_game_mode = st.text_input("Game Mode", value=selected_row.get('game_mode', '') or "")
                                    new_game_level = st.number_input("Game Level/Wave", value=int(selected_row.get('game_level', 0) or 0), min_value=0, step=1)
                                    win_options=[None, 'Win', 'Loss']; current_win=selected_row.get('win'); default_win_idx=1 if current_win == 1 else 2 if current_win == 0 else 0
                                    new_win_sel = st.selectbox("Win/Loss", win_options, index=default_win_idx)
                                    win_val_edit = 1 if new_win_sel == 'Win' else 0 if new_win_sel == 'Loss' else None
                                    new_is_ranked = st.checkbox("Ranked?", value=selected_row.get('ranked') == 1)
                                    new_pre_rank, new_post_rank = selected_row.get('pre_match_rank_value'), selected_row.get('post_match_rank_value')
                                    if new_is_ranked:
                                        edit_game_id = selected_row.get('game_id'); ranks = get_game_ranks(edit_game_id) if edit_game_id else []; rank_opts = ["Unranked"] + ranks
                                        pre_rank_val = new_pre_rank or "Unranked"; pre_idx = rank_opts.index(pre_rank_val) if pre_rank_val in rank_opts else 0
                                        new_pre_rank = st.selectbox("Pre-match Rank", rank_opts, index=pre_idx)
                                        post_rank_val = new_post_rank or "Unranked"; post_idx = rank_opts.index(post_rank_val) if post_rank_val in rank_opts else 0
                                        new_post_rank = st.selectbox("Post-match Rank", rank_opts, index=post_idx)
                                    else: new_pre_rank, new_post_rank = None, None
                                    
                                    submitted_edit = st.form_submit_button("Update Entry")
                                    if submitted_edit:
                                        payload = {"stat_type": new_stat_type, "stat_value": int(new_stat_value), "game_mode": new_game_mode or None,
                                                   "game_level": int(new_game_level) or None, "win": win_val_edit, "ranked": 1 if new_is_ranked else 0,
                                                   "pre_match_rank_value": new_pre_rank, "post_match_rank_value": new_post_rank}
                                        auth_headers = get_auth_headers()
                                        if auth_headers:
                                            try:
                                                response=requests.put(f"{FLASK_API_URL}/update_stats/{stat_id_to_edit}", json=payload, headers=auth_headers)
                                                response.raise_for_status(); st.success("Entry updated!"); clear_edit_cache(); st.rerun()
                                            except requests.exceptions.RequestException as e:
                                                st.error(f"Update error: {e}")
                                                # (Full error handling)
                                    
                    else: st.info("No recent stats loaded or available for editing.")

    # --- Delete Tab (Trusted User Only) ---
    if st.session_state.is_trusted_user:
        with tabs[2]:
            st.subheader("Delete Data")
            delete_tabs = st.tabs(["Delete Player", "Delete Game", "Delete Stat"])

            # --- Delete Player ---
            with delete_tabs[0]:
                st.markdown("Select a player to delete. **Warning: This will delete the player AND all associated stats forever.**")
                if st.button("Load Players to Delete", key="load_delete_player_button"):
                    st.session_state.recent_players_df = pd.DataFrame(get_all_players())
                    st.session_state.player_delete_data_loaded = True
                    st.session_state.player_delete_confirmed = False
                    st.rerun()
                
                if st.session_state.player_delete_data_loaded:
                    players_df_del = st.session_state.recent_players_df
                    if not players_df_del.empty:
                        player_name_to_id_del = {p["player_name"]: p["player_id"] for index, p in players_df_del.iterrows()}
                        player_options_del = ["- Select player -"] + list(player_name_to_id_del.keys())
                        selected_player_name_to_del = st.selectbox("Select Player to Delete", player_options_del, key="delete_player_select", index=0)

                        if selected_player_name_to_del and selected_player_name_to_del != "- Select player -":
                            player_id_to_delete = player_name_to_id_del[selected_player_name_to_del]
                            st.warning(f"You are about to delete **{selected_player_name_to_del}** (ID: {player_id_to_delete}) and all their stats.")
                            
                            if not st.session_state.player_delete_confirmed:
                                if st.button("Confirm Delete Player", key="confirm_delete_player_button"):
                                    st.session_state.player_delete_confirmed = True; st.rerun()
                            
                            if st.session_state.player_delete_confirmed:
                                st.error("This action is permanent.")
                                if st.button("DELETE PLAYER FOREVER", key="final_delete_player"):
                                    auth_headers = get_auth_headers()
                                    if auth_headers:
                                        try:
                                            response = requests.delete(f"{FLASK_API_URL}/delete_player/{player_id_to_delete}", headers=auth_headers)
                                            response.raise_for_status()
                                            st.success(f"Player '{selected_player_name_to_del}' and all stats deleted.")
                                            clear_delete_cache(); st.rerun()
                                        except requests.exceptions.RequestException as e:
                                            st.error(f"Error deleting player: {e}")
                                            # (Full error handling)
                    else: st.info("No players found for your account.")
            
            # --- Delete Game ---
            with delete_tabs[1]:
                st.markdown("Select a game to delete. **Note: You can only delete games that have zero associated stats.**")
                if st.button("Load Games to Delete", key="load_delete_game_button"):
                    st.session_state.recent_games_df = pd.DataFrame(get_all_games())
                    st.session_state.game_delete_data_loaded = True
                    st.session_state.game_delete_confirmed = False
                    st.rerun()

                if st.session_state.game_delete_data_loaded:
                    games_df_del = st.session_state.recent_games_df
                    if not games_df_del.empty:
                        game_name_to_id_del = {g["game_name"]: g["game_id"] for index, g in games_df_del.iterrows()}
                        game_options_del = ["- Select game -"] + list(game_name_to_id_del.keys())
                        selected_game_name_to_del = st.selectbox("Select Game to Delete", game_options_del, key="delete_game_select", index=0)

                        if selected_game_name_to_del and selected_game_name_to_del != "- Select game -":
                            game_id_to_delete = game_name_to_id_del[selected_game_name_to_del]
                            st.warning(f"You are attempting to delete **{selected_game_name_to_del}** (ID: {game_id_to_delete}). This will only work if all stats are removed first.")

                            if not st.session_state.game_delete_confirmed:
                                if st.button("Confirm Delete Game", key="confirm_delete_game_button"):
                                    st.session_state.game_delete_confirmed = True; st.rerun()

                            if st.session_state.game_delete_confirmed:
                                st.error("This action is permanent.")
                                if st.button("DELETE GAME FOREVER", key="final_delete_game"):
                                    auth_headers = get_auth_headers()
                                    if auth_headers:
                                        try:
                                            response = requests.delete(f"{FLASK_API_URL}/delete_game/{game_id_to_delete}", headers=auth_headers)
                                            response.raise_for_status()
                                            st.success(f"Game '{selected_game_name_to_del}' deleted.")
                                            clear_delete_cache(); st.rerun()
                                        except requests.exceptions.RequestException as e:
                                            st.error(f"Error deleting game: {e}")
                                            if 'response' in locals() and response is not None and response.status_code == 409:
                                                st.error(f"Delete failed: {response.json().get('error')}")
                                    
                    else: st.info("No games found associated with your stats.")
            
            # --- Delete Stat ---
            with delete_tabs[2]:
                st.markdown("This is for deleting individual stat entries (e.g., a single match).")
                if st.button("Load Data for Deletion", key="load_delete_data_button_stat"):
                    st.session_state.recent_stats_df = get_recent_stats_for_display()
                    st.session_state.stat_delete_data_loaded = True; st.session_state.stat_delete_confirmed = False; st.rerun()
                
                if st.session_state.get('last_deleted_game_id'):
                    st.warning(f"You deleted the last stat for Game ID {st.session_state.last_deleted_game_id}. Do you want to delete the game entry itself?")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Yes, Delete Game Entry Now", key="prompt_delete_game", use_container_width=True):
                            auth_headers = get_auth_headers()
                            if auth_headers:
                                try:
                                    game_id_to_del = st.session_state.last_deleted_game_id
                                    response = requests.delete(f"{FLASK_API_URL}/delete_game/{game_id_to_del}", headers=auth_headers)
                                    response.raise_for_status()
                                    st.success(f"Game ID {game_id_to_del} successfully deleted.")
                                    st.session_state.last_deleted_game_id = None
                                    clear_delete_cache(); st.rerun()
                                except requests.exceptions.RequestException as e:
                                    st.error(f"Error deleting game: {e}")
                                    if 'response' in locals() and response is not None and response.status_code == 409:
                                        st.error(f"Delete failed: {response.json().get('error')}")
                            st.session_state.last_deleted_game_id = None
                    with col2:
                        if st.button("No, Keep Game Entry", key="prompt_keep_game", use_container_width=True):
                            st.session_state.last_deleted_game_id = None
                            st.rerun()


                if st.session_state.stat_delete_data_loaded:
                    recent_stats_df_del = st.session_state.recent_stats_df
                    if not recent_stats_df_del.empty:
                        def format_del_text(row):
                            text = f"({row['stat_id']}) {row['game_name']} {row['stat_type']} {row['stat_value']} by {row['player_name']} @ {row['played_at'].strftime('%y-%m-%d %H:%M')}"
                            if row['ranked'] == 1: text += f" (R:{row.get('pre_match_rank_value','?')}-{row.get('post_match_rank_value','?')})"
                            return text
                        recent_stats_df_del['display_text'] = recent_stats_df_del.apply(format_del_text, axis=1)
                        selected_entry_del = st.selectbox("Select entry to delete:", recent_stats_df_del['display_text'], key="del_select_stat", index=None)

                        if selected_entry_del:
                            selected_row_del = recent_stats_df_del[recent_stats_df_del['display_text'] == selected_entry_del].iloc[0]
                            stat_id_to_delete = int(selected_row_del['stat_id'])
                            
                            if not st.session_state.stat_delete_confirmed:
                                if st.button("Confirm Delete Selection", key="confirm_delete_button_stat"): st.session_state.stat_delete_confirmed = True; st.rerun()
                            if st.session_state.stat_delete_confirmed:
                                st.warning(f"DELETE entry?\n'{selected_entry_del}'")
                                if st.button("DELETE FOREVER", key="final_delete_button_stat"):
                                    auth_headers = get_auth_headers()
                                    if auth_headers:
                                        try:
                                            response = requests.delete(f"{FLASK_API_URL}/delete_stats/{stat_id_to_delete}", headers=auth_headers)
                                            response.raise_for_status()
                                            response_data = response.json()
                                            st.success("Entry deleted!")
                                            
                                            if response_data.get("last_stat_deleted") == True:
                                                st.session_state.last_deleted_game_id = response_data.get("game_id")
                                            
                                            clear_delete_cache(); st.rerun()
                                        except requests.exceptions.RequestException as e:
                                            st.error(f"Delete error: {e}")
                                            # (Full error handling)
                    else: st.info("No recent stats loaded or available for deletion.")

# --- Registered Guest View (Not Trusted, but logged in) ---
elif st.session_state.auth_mode == 'logged_in' and not st.session_state.is_trusted_user:
    st.info("You are logged in as a Guest. You can view stats associated with your account, but cannot add or edit data.")
    st.subheader("Recent Stats (View Only)")
    guest_stats_df = get_recent_stats_for_display(limit=20)
    if not guest_stats_df.empty:
        display_df = guest_stats_df[['played_at', 'game_name', 'player_name', 'stat_type', 'stat_value', 'win', 'ranked', 'pre_match_rank_value', 'post_match_rank_value']].copy()
        display_df['played_at'] = display_df['played_at'].dt.strftime('%Y-%m-%d %H:%M')
        display_df['win'] = display_df['win'].apply(lambda x: 'Win' if x == 1 else 'Loss' if x == 0 else 'N/A')
        display_df['ranked'] = display_df['ranked'].apply(lambda x: 'Yes' if x == 1 else 'No')
        display_df.fillna('N/A', inplace=True)
        st.dataframe(display_df, use_container_width=True)
    else:
        st.write("No recent stats to display for your account.")

# Footer
st.markdown("---")
st.markdown("Made with💡by [BOL](https://youtube.com/@TheBOLGuide)")