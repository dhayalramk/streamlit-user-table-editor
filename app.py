
import streamlit as st
import boto3
import json
import pandas as pd

# --- CONFIG ---
BUCKET = st.secrets["BUCKET"]
KEY = st.secrets["KEY"]
REGION = st.secrets["REGION"]

# --- AWS S3 Helpers ---
def load_data():
    s3 = boto3.client('s3', region_name=REGION,
                      aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
                      aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"])
    obj = s3.get_object(Bucket=BUCKET, Key=KEY)
    return json.loads(obj['Body'].read())

def save_data(data):
    s3 = boto3.client('s3', region_name=REGION,
                      aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
                      aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"])
    s3.put_object(Bucket=BUCKET, Key=KEY, Body=json.dumps(data, indent=2))

# --- App UI ---
st.set_page_config(page_title="Client Table Editor", layout="wide")
st.title("📋 Client User Table")

password = st.text_input("Enter Password", type="password")
if password != st.secrets["APP_PASSWORD"]:
    st.warning("Unauthorized")
    st.stop()

data = load_data()
df = pd.DataFrame(data)

st.subheader("🧾 Editable Table")
edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

if st.button("💾 Save Changes"):
    save_data(edited_df.to_dict(orient="records"))
    st.success("✅ Changes saved to S3.")
