import streamlit as st

# --- GOOGLE SITE VERIFICATION ---
st.markdown(
    '<meta name="google-site-verification" content="lPYdHOgd3-kVW7mLpGyL4c7RJuTq_BVM1wJS_6eqnc8" />',
    unsafe_allow_html=True
)

st.write(
    """
    Welcome to the Video Game Stats Tracker!

    This application allows you to log, track, and manage your personal video game statistics.
    
    ### Features:
    - **Admin Access:** Log in with a trusted Google account to unlock full data entry capabilities.
    - **Enter Stats:** Add new players, games (with genres), and detailed match stats.
    - **Edit Data:** Correct typos or update details for players, games, or individual stat entries.
    - **Delete Data:** Safely remove players, games (if empty), or specific stat records.
    - **Guest Mode:** Logged-in guests can view their own stats. Anonymous guests can explore the UI.
    
    Please use the **sidebar** to log in or navigate.
    """
)

# Footer
st.markdown("---")
st.markdown("Made with💡by [BOL](https://youtube.com/@TheBOLGuide)")