import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import csv
from io import StringIO
from datetime import datetime
import json
import time

# --- Configuration ---
ADMIN_PASSWORD = "ayodhya2025"
COLLECTION_NAME = "duty_cards_public"
APP_ID = "your_app_id_here" # REPLACE THIS with your actual __app_id if known, or any unique ID

# --- Firebase Initialization ---
def initialize_firebase():
    """Initializes Firebase Admin SDK using the service account key."""
    if not firebase_admin._apps:
        try:
            # Assumes serviceAccountKey.json is in the same directory
            cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred)
            st.session_state.db = firestore.client()
        except FileNotFoundError:
            st.error("🚨 Error: 'serviceAccountKey.json' not found. Please follow the setup instructions.")
            return False
        except Exception as e:
            st.error(f"🚨 Firebase Initialization Failed: {e}")
            return False
    return True

# --- State Management & Initialization ---

if 'db' not in st.session_state:
    st.session_state.db = None
if 'app_mode' not in st.session_state:
    st.session_state.app_mode = 'select' # 'select', 'admin', 'personnel'
if 'personnel_list' not in st.session_state:
    st.session_state.personnel_list = []
if 'searched_card' not in st.session_state:
    st.session_state.searched_card = None

def get_collection_ref():
    """Constructs the full Firestore path based on the Canvas structure."""
    if st.session_state.db:
        path = f"artifacts/{APP_ID}/public/data/{COLLECTION_NAME}"
        return st.session_state.db.collection(path)
    return None

# --- Data Fetching (Caching for efficiency) ---
@st.cache_data(ttl=5) # Cache data for 5 seconds
def fetch_all_duty_cards():
    """Fetches all records for the admin view."""
    collection_ref = get_collection_ref()
    if collection_ref:
        docs = collection_ref.stream()
        records = []
        for doc in docs:
            data = doc.to_dict()
            # Convert Firestore timestamp to string for display
            if 'createdAt' in data and data['createdAt'] is not None:
                data['createdAt'] = data['createdAt'].strftime('%Y-%m-%d %H:%M:%S')
            records.append({"id": doc.id, **data})
        # Sort by creation time (newest first)
        records.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
        st.session_state.personnel_list = records
        return records
    return []

# --- Data Submission Functions ---

def submit_duty_card(data):
    """Submits a single duty card to Firestore."""
    collection_ref = get_collection_ref()
    if not collection_ref:
        st.error("Database not connected.")
        return False

    try:
        data_to_save = {
            "name": data.get("name", ""),
            "mobileNumber": data.get("mobileNumber", ""),
            "dutyLocation": data.get("dutyLocation", "श्रीरामजन्मभूमि मन्दिर ध्वजारोहण समारोह – 2025"),
            "dutyTime": data.get("dutyTime", ""),
            "zone": data.get("zone", ""),
            "zonalInCharge": data.get("zonalInCharge", ""),
            "sector": data.get("sector", ""),
            "sectorInCharge": data.get("sectorInCharge", ""),
            "authority": "वरिष्ठ पुलिस अधीक्षक, अयोध्या",
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
        collection_ref.add(data_to_save)
        st.success("✅ Duty Card saved successfully!")
        # Force cache clear after write
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"❌ Submission Failed: {e}")
        return False

def parse_and_upload_csv(uploaded_file):
    """Parses CSV content and uploads records in batches."""
    if not uploaded_file:
        return

    string_data = StringIO(uploaded_file.getvalue().decode("utf-8"))
    reader = csv.DictReader(string_data)
    
    records = []
    # Headers to look for (case-sensitive as per original JS app)
    valid_keys = ['name', 'mobileNumber', 'dutyLocation', 'dutyTime', 'zone', 'zonalInCharge', 'sector', 'sectorInCharge']

    # Map headers to standard keys, cleaning up user-provided headers
    header_map = {h.strip(): h.strip() for h in reader.fieldnames if h.strip() in valid_keys}

    for row in reader:
        record = {
            "authority": "वरिष्ठ पुलिस अधीक्षक, अयोध्या",
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
        has_content = False
        
        for key in valid_keys:
            # Find the corresponding value from the row, default to empty string
            value = row.get(key, "").strip()
            record[key] = value
            if value:
                has_content = True

        if has_content:
            records.append(record)
    
    if not records:
        st.warning("No valid records found in the CSV.")
        return

    collection_ref = get_collection_ref()
    if not collection_ref:
        st.error("Database not connected for bulk upload.")
        return
        
    # Batch uploading to Firestore
    batch = st.session_state.db.batch()
    batch_count = 0
    total_uploaded = 0
    
    st.info(f"Uploading {len(records)} records in batches...")
    
    for record in records:
        doc_ref = collection_ref.document()
        batch.set(doc_ref, record)
        batch_count += 1
        total_uploaded += 1

        if batch_count >= 500:
            batch.commit()
            st.success(f"Uploaded {total_uploaded} records so far...")
            batch = st.session_state.db.batch()
            batch_count = 0

    if batch_count > 0:
        batch.commit()
        
    st.success(f"🎉 Successfully uploaded {total_uploaded} records!")
    st.cache_data.clear()


# --- UI Components (Streamlit) ---

def display_duty_card(data, mode="admin"):
    """Displays a single duty card in a styled format."""
    st.markdown(f"""
    <div style="padding: 15px; margin-bottom: 10px; border-left: 5px solid #b91c1c; border-radius: 5px; background-color: #fef2f2; box-shadow: 2px 2px 8px rgba(0,0,0,0.1);">
        <h4 style="color: #991b1b; margin-bottom: 5px; font-weight: 800;">{data.get('name') or 'N/A'}</h4>
        <p style="font-size: 0.9em; margin: 2px 0;"><span style="font-weight: 600;">ड्यूटी स्थल:</span> {data.get('dutyLocation') or 'N/A'}</p>
        <p style="font-size: 0.9em; margin: 2px 0;"><span style="font-weight: 600;">मोबाइल नंबर:</span> {data.get('mobileNumber') or 'N/A'}</p>
        <p style="font-size: 0.9em; margin: 2px 0;"><span style="font-weight: 600;">समय:</span> {data.get('dutyTime') or 'N/A'}</p>
        <hr style="border-top: 1px solid #fee2e2; margin: 8px 0;">
        <div style="display: flex; justify-content: space-between; font-size: 0.85em;">
            <div><span style="font-weight: 600;">जोन:</span> {data.get('zone') or 'N/A'}</div>
            <div><span style="font-weight: 600;">सेक्टर:</span> {data.get('sector') or 'N/A'}</div>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 0.85em;">
            <div><span style="font-weight: 600;">जोन प्रभारी:</span> {data.get('zonalInCharge') or 'N/A'}</div>
            <div><span style="font-weight: 600;">सेक्टर प्रभारी:</span> {data.get('sectorInCharge') or 'N/A'}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_admin_view():
    """Renders the Admin view with forms, bulk upload, and list."""
    st.title("🛡️ Admin Duty Card Management")

    # --- Back Button ---
    if st.button("⬅️ Back to Selection", key="admin_back"):
        st.session_state.app_mode = 'select'
        return

    # --- Single Entry Form ---
    st.header("1. Single Personnel Assignment")
    with st.form(key='single_entry_form'):
        cols = st.columns(2)
        with cols[0]:
            name = st.text_input("Name (नाम)")
            mobileNumber = st.text_input("Mobile Number (मोबाइल नंबर)", help="Required for personnel search.")
        with cols[1]:
            dutyLocation = st.text_input("Duty Location (ड्यूटी स्थल)", value="श्रीरामजन्मभूमि मन्दिर ध्वजारोहण समारोह – 2025")
            dutyTime = st.text_input("Duty Time (ड्यूटी का समय)", placeholder="e.g., 08:00 AM - 04:00 PM")
            
        cols = st.columns(2)
        with cols[0]:
            zone = st.text_input("Zone (जोन)")
            zonalInCharge = st.text_input("Zonal In-Charge (जोन प्रभारी)")
        with cols[1]:
            sector = st.text_input("Sector (सेक्टर)")
            sectorInCharge = st.text_input("Sector In-Charge (सेक्टर प्रभारी)")

        if st.form_submit_button("💾 Save Duty Card"):
            data = locals()
            submit_duty_card(data)
            
    # --- Bulk Upload ---
    st.header("2. Bulk CSV Upload")
    uploaded_file = st.file_uploader("Upload CSV File", type=["csv"], help="Headers must be: name, mobileNumber, dutyLocation, dutyTime, zone, zonalInCharge, sector, sectorInCharge")
    if uploaded_file and st.button("🚀 Process & Upload CSV"):
        parse_and_upload_csv(uploaded_file)
    
    # --- Personnel List ---
    st.header(f"3. Personnel List ({len(st.session_state.personnel_list)} Records)")
    
    # Reload button
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.session_state.personnel_list = fetch_all_duty_cards()
        st.success("Data refreshed!")

    if st.session_state.personnel_list:
        for record in st.session_state.personnel_list:
            display_duty_card(record)
    else:
        st.info("No records found in the database.")

def render_personnel_view():
    """Renders the Personnel view for mobile number search."""
    st.title("👤 View My Duty Card")
    st.subheader("Enter your registered mobile number")

    # --- Back Button ---
    if st.button("⬅️ Back to Selection", key="personnel_back"):
        st.session_state.app_mode = 'select'
        st.session_state.searched_card = None
        return

    # --- Search Form ---
    with st.form(key='mobile_search_form'):
        mobile_number = st.text_input("Mobile Number (मोबाइल नंबर)", key="search_mobile")
        
        if st.form_submit_button("🔍 Search Card"):
            st.session_state.searched_card = None
            
            if not mobile_number:
                st.warning("Please enter a mobile number to search.")
                return

            collection_ref = get_collection_ref()
            if not collection_ref:
                st.error("Database not connected.")
                return

            try:
                # Query Firestore for the mobile number
                query_result = collection_ref.where('mobileNumber', '==', mobile_number.strip()).limit(1).stream()
                
                found = False
                for doc in query_result:
                    st.session_state.searched_card = doc.to_dict()
                    found = True
                    break
                
                if found:
                    st.success(f"Duty card found for mobile number: {mobile_number}")
                else:
                    st.warning(f"No duty card found for mobile number: {mobile_number}")

            except Exception as e:
                st.error(f"Search Failed: {e}")

    # --- Display Result ---
    if st.session_state.searched_card:
        st.header("Your Assigned Duty")
        display_duty_card(st.session_state.searched_card, mode="personnel")


def render_mode_selection():
    """Renders the initial screen for mode selection."""
    st.title("Duty Card System Access")
    
    st.header("Personnel Access")
    st.info("View your individual duty card by entering your mobile number.")
    if st.button("View My Duty Card", key="select_personnel"):
        st.session_state.app_mode = 'personnel'
        st.session_state.searched_card = None # Clear any previous search

    st.markdown("---")
    
    st.header("Admin Management")
    st.info("Enter the admin password to access data entry and full list.")
    
    admin_password_input = st.text_input("Admin Password", type="password", key="admin_pass_input")
    
    if st.button("Login to Admin", key="select_admin"):
        if admin_password_input == ADMIN_PASSWORD:
            st.session_state.app_mode = 'admin'
            fetch_all_duty_cards() # Load data immediately
        else:
            st.error("Invalid password.")

# --- Main Application Loop ---

def main():
    st.set_page_config(page_title="Duty Card System", layout="centered")

    st.markdown("""
    <style>
        .stButton>button {
            width: 100%;
            border-radius: 8px;
            background-color: #b91c1c; /* Tailwind red-700 */
            color: white;
            font-weight: 600;
        }
        .stButton>button:hover {
            background-color: #991b1b; /* Tailwind red-800 */
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Attempt to initialize Firebase first
    if not initialize_firebase():
        return # Stop if Firebase initialization fails

    if st.session_state.db is None:
        st.warning("Attempting to connect to Firebase...")
        time.sleep(1) # Give a moment for connection attempt
        if st.session_state.db is None:
            return

    # Render view based on current app mode
    if st.session_state.app_mode == 'select':
        render_mode_selection()
    elif st.session_state.app_mode == 'admin':
        render_admin_view()
    elif st.session_state.app_mode == 'personnel':
        render_personnel_view()

# --- Entry Point (Ensures main() runs when the script is executed) ---
if __name__ == "_main_":
    main()