# Pages

Streamlit multi-page app pages. Each file is a separate page in the Streamlit navigation sidebar.

## Files

| File | Page | Purpose |
|------|------|---------|
| `1_Home.py` | Home | Landing page with app overview and navigation |
| `2_Stats.py` | Stats | Main stats entry and visualization interface |
| `3_Privacy_Policy.py` | Privacy Policy | Required for Instagram Graph API approval |
| `4_Terms_of_Service.py` | Terms of Service | Required for Instagram Graph API approval |
| `5_Data_Deletion.py` | Data Deletion | Required for Instagram Graph API approval — user data removal instructions |

## Running the App

From the project root in VS Code terminal:

```bash
streamlit run game_tracker_streamlit_app.py
```

Streamlit automatically picks up all files in `pages/` as additional navigation pages.

## Adding a New Page

1. Create a new file in `pages/` with a number prefix for ordering:
   ```
   pages/6_My_New_Page.py
   ```
2. Add standard Streamlit imports at the top:
   ```python
   import streamlit as st

   st.title("My New Page")
   st.write("Content here")
   ```
3. The page appears automatically in the sidebar — no registration needed.

## Notes on Policy Pages

`3_Privacy_Policy.py`, `4_Terms_of_Service.py`, and `5_Data_Deletion.py` are required by Meta's Instagram Graph API review process. They must be publicly accessible. These pages are deployed via the Streamlit Cloud app at the live URL.
