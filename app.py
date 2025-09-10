import streamlit as st
import boto3
import json
import pandas as pd
import requests

# ---------- CONFIG ----------
BUCKET = st.secrets["BUCKET"]
KEY = st.secrets["KEY"]
REGION = st.secrets["REGION"]
AWS_ACCESS_KEY_ID = st.secrets["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = st.secrets["AWS_SECRET_ACCESS_KEY"]

BROKER_OPTIONS = ["ANGEL"]
APP_PASSWORD = st.secrets["APP_PASSWORD"]

TELEGRAM_BOT_TOKEN = st.secrets["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        r = requests.post(url, data=payload)
        r.raise_for_status()
    except Exception as e:
        st.error(f"⚠️ Failed to send Telegram message: {e}")

# ---------- AUTH ----------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 Authentication Required")
    password_input = st.text_input("Enter app password", type="password")

    if st.button("Login"):
        if password_input == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ Incorrect password. Please try again.")
    st.stop()

# ---------- S3 HELPERS ----------
def get_s3_client():
    return boto3.client(
        "s3",
        region_name=REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )

def load_users():
    s3 = get_s3_client()
    obj = s3.get_object(Bucket=BUCKET, Key=KEY)
    return json.loads(obj['Body'].read())

def save_users(users):
    s3 = get_s3_client()
    try:
        s3.put_object(Bucket=BUCKET, Key=KEY, Body=json.dumps(users, indent=2))
        st.success("✅ Changes saved to S3")
        send_telegram_message("✅ User Manager: Changes saved to S3 successfully.")
    except Exception as e:
        st.error(f"❌ Failed to save changes: {e}")
        send_telegram_message(f"❌ User Manager: Failed to save changes.\nError: {e}")

# ---------- MAIN UI ----------
st.set_page_config(page_title="User Manager", layout="wide")
st.title("👥 User Management Panel")

users = load_users()
df = pd.DataFrame(users)

# Ensure all required columns exist
columns = [
    "name", "broker", "client_id", "api_secret", "api_key", "totp_secret", "password",
    "lots", "active", "mobile", "email", "sl", "target"
]
for col in columns:
    if col not in df.columns:
        df[col] = "" if col not in ["lots", "active", "sl", "target"] else 0

# Normalize broker values
df["broker"] = df["broker"].astype(str).str.upper().str.strip()
df.loc[~df["broker"].isin(BROKER_OPTIONS), "broker"] = "ANGEL"

# ---------- SEARCH ----------
search = st.text_input("🔍 Search Users (name/email/client_id)", "")
filtered_df = df[df.apply(
    lambda row: any(search.lower() in str(row[c]).lower() for c in ["name", "email", "client_id"]),
    axis=1
)].reset_index(drop=True)

# ---------- EDITABLE TABLE ----------
st.markdown("### 📋 User List (Editable)")

edited_df = st.data_editor(
    filtered_df,
    use_container_width=True,
    num_rows="dynamic",
    column_config={
        "broker": st.column_config.SelectboxColumn("Broker", options=BROKER_OPTIONS, required=True),
        "active": st.column_config.CheckboxColumn("Active", default=True),
        "lots": st.column_config.NumberColumn("Lots", min_value=0, step=1),
        "sl": st.column_config.NumberColumn("Stop Loss", min_value=0, step=1),
        "target": st.column_config.NumberColumn("Target", min_value=0, step=1),
    }
)

# ---------- SAVE CHANGES ----------
if st.button("💾 Save All Changes"):
    for i in edited_df.index:
        edited_row = edited_df.loc[i].copy()
        edited_row["active"] = int(bool(edited_row["active"]))
        cid = edited_row["client_id"]

        match_idx = df[df["client_id"] == cid].index
        if not match_idx.empty:
            for col in df.columns:
                df.at[match_idx[0], col] = edited_row.get(col, df.at[match_idx[0], col])

    save_users(df.to_dict(orient="records"))
    st.success("✅ All changes saved successfully.")

# ---------- DELETE USERS ----------
st.markdown("### 🗑️ Delete Users")

delete_df = st.data_editor(
    filtered_df.assign(delete=False),
    use_container_width=True,
    column_config={
        "delete": st.column_config.CheckboxColumn("Delete", default=False),
    },
    hide_index=True,
    num_rows="fixed"
)

if st.button("🗑️ Delete Selected Users"):
    to_delete = delete_df[delete_df["delete"] == True]["client_id"].tolist()
    if not to_delete:
        st.warning("⚠️ No users selected for deletion.")
    else:
        df = df[~df["client_id"].isin(to_delete)].reset_index(drop=True)
        save_users(df.to_dict(orient="records"))
        st.success(f"✅ Deleted {len(to_delete)} user(s).")
        send_telegram_message(f"🗑️ User Manager: Deleted {len(to_delete)} user(s).")
        st.rerun()

# ---------- ADD USER ----------
st.markdown("---")
st.subheader("➕ Add New User")

with st.form("add_user_form"):
    new_user = {}
    cols1 = st.columns(4)
    new_user["name"] = cols1[0].text_input("👤 Name")
    new_user["broker"] = cols1[1].selectbox("🏦 Broker", BROKER_OPTIONS)
    new_user["client_id"] = cols1[2].text_input("🆔 Client ID")
    new_user["mobile"] = cols1[3].text_input("📞 Mobile")

    cols2 = st.columns(4)
    new_user["email"] = cols2[0].text_input("📧 Email")
    new_user["password"] = cols2[1].text_input("🔑 Password")
    new_user["api_key"] = cols2[2].text_input("🔐 API Key")
    new_user["api_secret"] = cols2[3].text_input("🔐 API Secret")

    cols3 = st.columns(4)
    new_user["totp_secret"] = cols3[0].text_input("📟 TOTP Secret")
    new_user["lots"] = cols3[1].number_input("🎯 Lots", min_value=0, step=1)
    new_user["sl"] = cols3[2].number_input("🛡️ Stop Loss", min_value=0, step=1)
    new_user["target"] = cols3[3].number_input("🏁 Target", min_value=0, step=1)

    new_user["active"] = st.checkbox("✅ Active", value=True)

    submitted = st.form_submit_button("➕ Add User")
    if submitted:
        new_user["active"] = int(new_user["active"])
        if new_user["client_id"] in df["client_id"].values:
            st.warning("⚠️ User with this Client ID already exists.")
        else:
            df = pd.concat([df, pd.DataFrame([new_user])], ignore_index=True)
            save_users(df.to_dict(orient="records"))
            st.success(f"✅ Added user {new_user['name']}")
            st.rerun()
