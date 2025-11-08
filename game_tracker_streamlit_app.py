import streamlit as st
import pandas as pd # Import pandas for session state
from utils import (
    attempt_flask_login, 
    register_guest_user, 
    DB_URL, 
    DB_NAME, 
    DB_USER, 
    DB_PASSWORD,
    API_KEY,
    TRUSTED_EMAILS
)

# Validate essential secrets
if not API_KEY:
    st.error("API_KEY must be set in Streamlit secrets.")
    st.stop()
if not all([DB_URL, DB_NAME, DB_USER, DB_PASSWORD]):
    st.error("Redshift database connection details (DB_URL, DB_NAME, DB_USER, DB_PASSWORD) must be set in Streamlit secrets.")
    st.stop()
if not TRUSTED_EMAILS:
    st.warning("TRUSTED_EMAILS list is not set or empty in Streamlit secrets. No users will be treated as admin.")
     
# --- Page Config ---
st.set_page_config(layout="wide", page_title="Video Game Stats Tracker", page_icon="🎮")

# --- Session State Initialization ---
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
if 'is_registered_guest' not in st.session_state:
    st.session_state.is_registered_guest = False
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

# --- Guest-specific state ---
if 'guest_selected_genre' not in st.session_state:
    st.session_state.guest_selected_genre = "Select a Genre"
if 'guest_selected_subgenre' not in st.session_state:
    st.session_state.guest_selected_subgenre = "Select a Subgenre"
    
# --- Authentication Logic (Global) ---
# This logic runs on every page load to ensure the user's
# state is always correct.

# 1. Check if already logged in via Streamlit Cloud's st.user
current_user_email = getattr(st.user, "email", None)

# 2. Handle state transitions
if st.session_state.auth_mode == 'guest' and current_user_email:
    print(f"Detected Streamlit Cloud user {current_user_email} while in guest mode. Processing...")
    if current_user_email in TRUSTED_EMAILS:
        attempt_flask_login(current_user_email)
    else:
        register_guest_user(current_user_email)
    st.rerun()

elif st.session_state.auth_mode == 'prompt_login':
    st.login("google")
    current_user_email_after_prompt = getattr(st.user, "email", None)
    if current_user_email_after_prompt:
        print(f"User {current_user_email_after_prompt} detected after st.login prompt.")
        st.session_state.email = current_user_email_after_prompt
        if current_user_email_after_prompt in TRUSTED_EMAILS:
            attempt_flask_login(current_user_email_after_prompt)
        else:
            register_guest_user(current_user_email_after_prompt)
        st.rerun()
    # else: User is still in Google flow or cancelled

# --- Define Pages ---
# These are the pages Streamlit will find in the pages/ directory
# We just define them here to control the navigation menu
home_page = st.Page("pages/1_Home.py", title="Home", icon="🏠", default=True)
stats_page = st.Page("pages/2_Stats.py", title="Video Games Stats Form", icon="🎮")
privacy_page = st.Page("pages/3_Privacy_Policy.py", title="Privacy Policy", icon="📄")
tos_page = st.Page("pages/4_Terms_of_Service.py", title="Terms of Service", icon="📜")

# --- Sidebar & Navigation ---
st.sidebar.title("Authentication")

if st.session_state.auth_mode in ('guest', 'login_failed'):
    st.sidebar.info("You are currently in Guest Mode.")
    if st.session_state.auth_mode == 'login_failed': st.sidebar.error("Previous login/registration failed.")
    col_login, col_guest = st.sidebar.columns(2)
    if col_login.button("Login with Google"): 
        st.session_state.auth_mode = 'prompt_login'
        st.rerun()
    col_guest.button("Continue as Guest", disabled=(st.session_state.auth_mode == 'guest'))
    
    # Navigation for Guests
    pg = st.navigation({
        "Main": [home_page],
        "Legal": [privacy_page, tos_page]
    })

elif st.session_state.auth_mode == 'prompt_login':
    st.sidebar.warning("Waiting for Google login completion...")
    pg = st.navigation({
        "Main": [home_page],
        "Legal": [privacy_page, tos_page]
        })


elif st.session_state.auth_mode == 'logged_in':
    if st.session_state.is_trusted_user:
        st.sidebar.success(f"Logged in as Admin: {st.session_state.email}")
        if not st.session_state.jwt_token and st.session_state.email:
             print("JWT token missing for logged-in trusted user, attempting recovery...")
             if not attempt_flask_login(st.session_state.email): 
                 st.error("Backend re-auth failed."); st.session_state.auth_mode = 'guest'; st.rerun()
             else: st.rerun()
        
        # --- Admin Navigation ---
        pg = st.navigation({
            "Main": [home_page],
            "Application": [stats_page],
            "Legal": [privacy_page, tos_page]
        })

    elif st.session_state.is_registered_guest:
        st.sidebar.info(f"Logged in as Registered Guest: {st.session_state.email}")
        
        # --- Registered Guest Navigation ---
        pg = st.navigation({
            "Main": [home_page],
            "Application": [stats_page], # Guest view of stats page
            "Legal": [privacy_page, tos_page]
        })

    else: 
        st.sidebar.error("Invalid auth state. Reverting to guest."); st.session_state.auth_mode = 'guest'; st.rerun()

    if st.sidebar.button("Logout"): 
        st.session_state.clear(); st.session_state.auth_mode = 'guest'
        print("Logout successful, resetting state."); 
        st.logout() # Clears st.user

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown(f"""
Made with💡by [BOL](https://youtube.com/@TheBOLGuide)
""")

# --- Main Page Content ---
st.markdown("<h1 style='text-align: center; color: #c8ac44'>🎮 Video Game Stats Entry</h1>", unsafe_allow_html=True)
st.markdown("---")

# Run the navigation
pg.run()