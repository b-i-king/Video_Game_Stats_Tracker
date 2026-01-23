import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from utils import (
    GENRES, FLASK_API_URL, 
    get_all_players, get_game_ranks, get_all_games, get_game_details,
    get_game_modes, get_game_stat_types, get_auth_headers, 
    add_stat_input, delete_stat_input, update_genre_state,
    update_guest_genre_state_callback, get_recent_stats_for_display, 
    clear_edit_cache, clear_delete_cache,
    get_game_franchises, get_game_installments, set_live_dashboard_state
)

# --- Page Guard ---
# Redirect to home if not logged in
if st.session_state.auth_mode != 'logged_in':
    st.warning("Please log in from the Home page to access this feature.")
    st.stop()

# --- Player Selection (Trusted Users Only) ---
if st.session_state.is_trusted_user:
    st.subheader("Select or add a player associated with your account.", divider="grey")
    players_list_data = get_all_players()
    player_name_to_id = {p["player_name"]: p["player_id"] for p in players_list_data}
    
    # Create the base list of player names from the DB
    player_names_from_db = list(player_name_to_id.keys())
    
    # Check if a player is already in session state (e.g., from a "new player" submit)
    # If they are, and they're NOT in the DB list yet, add them temporarily to the options
    temp_player_list = player_names_from_db
    if st.session_state.player_name and st.session_state.player_name not in player_names_from_db:
        temp_player_list = [st.session_state.player_name] + temp_player_list
    
    player_options = ["- Select player -", "Add a new player"] + temp_player_list

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
    
    # --- Guest Genre/Subgenre Logic ---
    guest_game_genre_selected = st.selectbox(
         "Game Genre *",
         list(GENRES.keys()),
         key="guest_new_game_genre_select", # Unique key
         index=list(GENRES.keys()).index(st.session_state.guest_selected_genre),
         on_change=update_guest_genre_state_callback # Use guest callback
    )
     
    guest_subgenre_options = GENRES.get(st.session_state.guest_selected_genre, ["Select a Subgenre"])
    guest_current_subgenre = st.session_state.guest_selected_subgenre
    if guest_current_subgenre not in guest_subgenre_options: guest_current_subgenre = guest_subgenre_options[0]
     
    guest_game_subgenre_selected = st.selectbox(
         "Game Subgenre *",
         guest_subgenre_options,
         key="guest_new_game_subgenre_select", # Unique key
         index=guest_subgenre_options.index(guest_current_subgenre) 
    )
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
        st.form_submit_button("Submit Form (Guest Mode)", disabled=True, help="This will not save data.")


elif st.session_state.auth_mode == 'prompt_login':
    st.info("Complete Google Login using the popup or sidebar.")

# --- Main Content Area (Tabs for Trusted, Guest UI for others) ---
if st.session_state.player_name and st.session_state.is_trusted_user:
    player_id = st.session_state.player_id
    
    tab_list = ["Enter Stats", "Edit", "Delete"]
    tabs = st.tabs(tab_list)

    # --- Enter Stats Tab ---
    with tabs[0]:
         # --- NEW GAME SELECTION (Franchise -> Installment) ---
        st.subheader("Game Selection")
        
        st.session_state.setdefault('selected_game_franchise', None)
        st.session_state.setdefault('selected_game_id', None)

        franchise_list = get_game_franchises()
        franchise_options = ["- Select Franchise -"] + sorted(list(set(franchise_list))) + ["(Enter New Franchise)"]
        
        if st.session_state.selected_game_franchise not in franchise_options:
             st.session_state.selected_game_franchise = "- Select Franchise -"
        
        selected_franchise_name = st.selectbox(
            "Select Game Name (Franchise)", 
            franchise_options, 
            index=franchise_options.index(st.session_state.selected_game_franchise),
            key="franchise_select_key",
            on_change=lambda: st.session_state.update(selected_game_franchise=st.session_state.franchise_select_key, selected_game_id=None), # Reset game on change
            help="Select existing game franchise or enter a new one."
        )
        
        final_game_franchise = selected_franchise_name
        new_franchise_input = ""
        is_new_franchise_mode = (selected_franchise_name == "(Enter New Franchise)")
        
        # --- Logic for New Franchise ---
        if is_new_franchise_mode:
            new_franchise_input = st.text_input("New Game Name (Franchise) *", help="e.g., Call of Duty, Elden Ring, Final Fantasy")
            final_game_franchise = new_franchise_input.strip() if new_franchise_input.strip() else None
            
            # --- Allow skipping installment ---
            new_installment_name_input = st.text_input("New Game Installment (Optional)", help="e.g., Black Ops 7. Leave BLANK if this is a standalone game.")
            final_game_installment = new_installment_name_input.strip() if new_installment_name_input.strip() else None
            
            is_new_installment_mode = True # We are defining a new game
            selected_game_id = None
        
        # --- Logic for Existing Franchise ---
        elif final_game_franchise and final_game_franchise != "- Select Franchise -":
            game_options_list = get_game_installments(final_game_franchise) # Returns list of dicts
            
            # The key from backend is 'installment_name'
            installment_name_to_id = {g['installment_name']: g['game_id'] for g in game_options_list}
            installment_name_options = ["- Select Installment -", "(Add New Installment)"] + list(installment_name_to_id.keys())
            
            current_game_id = st.session_state.get('selected_game_id')
            current_installment_name = None
            for name, gid in installment_name_to_id.items():
                if gid == current_game_id:
                    current_installment_name = name
                    break
            default_installment_index = installment_name_options.index(current_installment_name) if current_installment_name in installment_name_options else 0

            selected_installment_name = st.selectbox(
                "Select Game Installment", 
                installment_name_options, 
                key="installment_select_key",
                index=default_installment_index,
                on_change=lambda: st.session_state.update(selected_game_id=installment_name_to_id.get(st.session_state.installment_select_key)),
                help="Select existing installment or add a new one."
            )
            st.session_state.selected_game_id = installment_name_to_id.get(selected_installment_name)
            
            is_new_installment_mode = (selected_installment_name == "(Add New Installment)")
            selected_game_id = st.session_state.selected_game_id
            
            final_game_installment = selected_installment_name
            new_installment_name_input = ""
            
            if is_new_installment_mode:
                new_installment_name_input = st.text_input("New Game Installment *", help="e.g., Black Ops 7, Warzone.")
                final_game_installment = new_installment_name_input.strip() if new_installment_name_input.strip() else None
            elif selected_installment_name == "(Main Game)" or selected_installment_name == "- Select Installment -":
                final_game_installment = None # Send NULL
        
        else: # No franchise selected
            is_new_installment_mode = False
            selected_game_id = None
            final_game_installment = None
        
        # --- Add/Delete Stat Buttons ---
        with st.container(border=True):
            col_add_stat, col_del_stat = st.columns([1, 1])
            with col_add_stat: st.button("➕ Stat Row", key="add_stat_button", on_click=add_stat_input, use_container_width=True)
            with col_del_stat: st.button("➖ Stat Row", key="delete_stat_button", on_click=delete_stat_input, use_container_width=True)

        
        # --- Genre/Subgenre (Conditional, outside form) ---
        new_game_name_input, new_game_series_input = "", ""
        new_game_genre_selected, new_game_subgenre_selected = st.session_state.selected_genre, st.session_state.selected_subgenre

        if is_new_installment_mode:
            st.markdown("---"); st.subheader("New Game Genre Details")
            
            # Use a unique key for the genre selectbox
            new_game_genre_selected = st.selectbox( "Game Genre *", list(GENRES.keys()), help="Select the genre of the game", key="new_game_genre_select",
                index=list(GENRES.keys()).index(st.session_state.selected_genre), on_change=update_genre_state )
            
            subgenre_options = GENRES.get(st.session_state.selected_genre, ["Select a Subgenre"])
            current_subgenre = st.session_state.selected_subgenre
            if current_subgenre not in subgenre_options: current_subgenre = subgenre_options[0]
            # Use a unique key for the subgenre selectbox
            new_game_subgenre_selected = st.selectbox( "Game Subgenre *", subgenre_options, help="Select the subgenre of the game", key="new_game_subgenre_select",
                index=subgenre_options.index(current_subgenre) ) 
            st.markdown("---")
        
        # Determine final game details based on mode
        if is_new_installment_mode:
            final_game_name = new_game_name_input
            final_game_series = new_game_series_input
            final_game_genre = st.session_state.selected_genre # Read from state set by callback
            final_game_subgenre = new_game_subgenre_selected # Read from the widget
        else:
            final_game_name = final_game_franchise
            final_game_series, final_game_genre, final_game_subgenre = None, None, None
        
        # --- Set Live State Button ---
        if selected_game_id and player_id:
            if st.button("Set as Live Game for OBS", key="set_live_game", width="stretch"):
                set_live_dashboard_state(player_id, selected_game_id)
                st.success(f"OBS Dashboard set to: {st.session_state.player_name} @ {selected_installment_name}")
        
        # --- Set Live Status Toggle ---        
        st.markdown("---")
    
        # Initialize session state for live status if not exists
        if 'is_live_streaming' not in st.session_state:
            st.session_state.is_live_streaming = False
        
        # Live status toggle with visual indicator
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader("🔴 Streaming Status")
        with col2:
            # Toggle button with visual feedback
            is_live = st.toggle(
                "Live Now", 
                value=st.session_state.is_live_streaming,
                key="live_toggle",
                help="Enable this when you're LIVE streaming. Social media posts will include #Live #TheBroadcast"
            )
            st.session_state.is_live_streaming = is_live
        
        # Visual indicator
        if st.session_state.is_live_streaming:
            st.success("🔴 LIVE - Posts will include live stream links and hashtags")
        else:
            st.info("⚪ Offline - Posts will use standard format")
        
        st.markdown("---")
        
        # --- Stat Type Guidance ---
        if not is_new_installment_mode and selected_game_id:
            stat_types_list = get_game_stat_types(selected_game_id)
            if stat_types_list:
                if final_game_installment:
                    st.info(f"**Tip:** For '{final_game_franchise}: {final_game_installment}', you previously used these stat types: \n- " + "\n- ".join(stat_types_list))
                else:
                    st.info(f"**Tip:** For '{final_game_name}', you previously used these stat types: \n- " + "\n- ".join(stat_types_list))
    
        # --- Rank Selection Section (outside the form for reactivity) ---
        st.markdown("### Rank Information") 

        # Keep checkbox synced to session_state
        st.checkbox("Ranked?", help="Is this game mode a ranked match?",  key="is_ranked")

        # Dynamically render rank inputs when ranked
        if st.session_state.is_ranked:
            st.markdown("**Enter Rank Details**")
            pre_match_rank_final = "Unranked"
            post_match_rank_final = "Unranked"
            
            if not is_new_installment_mode and selected_game_id:
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
            st.markdown(f"**Entering stats for:** `{st.session_state.player_name}` | **Game:** `{final_game_franchise}` | **Installment:** `{final_game_installment or 'Main Game'}`")
            
            # --- Hybrid Game Mode Input ---
            game_mode_select_options = ["Main"]
            if not is_new_installment_mode and selected_game_id:
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
                if is_new_installment_mode:
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
                               "stats": stats_list, # stats_list now contains the rank data
                               "is_live": st.session_state.is_live_streaming 
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
                            stat_id_to_edit = int(selected_row['stat_id'])  # type: ignore
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