import streamlit as st
from utils.app_utils import YOUR_APP_HOME_URL

st.set_page_config(layout="wide", page_title="Privacy Policy", page_icon="📄")

st.title("Privacy Policy")

st.markdown(f"""
This Privacy Policy explains how we collect, use, and protect your information when you use the Video Game Stats Tracker application.

## 1. Information We Collect
When you log in using Google, we receive your email address from Google. We store this email address in our database (`dim.dim_users`) to identify you and determine your access level (Trusted Admin vs. Registered Guest).

## 2. How We Use Your Information
* **To Authenticate You:** Your email is your unique identifier for logging in.
* **To Authorize You:** We check your email against a `TRUSTED_EMAILS` list to grant admin privileges.
* **To Scope Data:** All data you create (players, games, stats) is linked to your user ID, so you can only see and manage your own data.

## 3. Information Sharing
We do not share your email address or any personal information with third parties. All data you enter is considered your own.

## 4. Data Storage
For trusted users, your email and game stat data are stored in a secure AWS Redshift Serverless database. For registered guest, only your email is stored in a secure AWS Redshift Serverless database. For guest users, no data is stored.

## 5. Contact
If you have any questions about this privacy policy, please contact the application administrator.

---
[Back to Home]({YOUR_APP_HOME_URL})
""")