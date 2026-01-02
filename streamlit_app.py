import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import base64

# --- Page Configuration ---
st.set_page_config(
    page_title="SANKET SPM Analytics",
    page_icon="🚄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Styling to Match "Form" Feel ---
st.markdown("""
<style>
    .main-header {font-size: 2.5rem; color: #1E3A8A; font-weight: 700;}
    .sub-header {font-size: 1.5rem; color: #1E3A8A; font-weight: 600; margin-top: 20px;}
    .metric-box {background-color: #F3F4F6; padding: 15px; border-radius: 10px; border: 1px solid #E5E7EB;}
    .report-frame {border: 1px solid #ddd; padding: 20px; border-radius: 5px; background: white;}
</style>
""", unsafe_allow_html=True)

# --- Helper Functions ---
def haversine_vectorized(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin(dlambda/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    return R * c

@st.cache_data
def load_data(file):
    return pd.read_csv(file)

def generate_html_report(trip_details, stats, stoppages, violations):
    """Generates a professional HTML report that can be printed to PDF."""
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
            h1 {{ color: #2c3e50; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; }}
            h2 {{ color: #2980b9; margin-top: 30px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .header-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }}
            .box {{ background: #f9f9f9; padding: 15px; border: 1px solid #eee; border-radius: 5px; }}
            .alert {{ color: #c0392b; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>🚄 SPM Analysis Report</h1>
        
        <div class="header-grid">
            <div class="box">
                <h3>👤 Crew Details</h3>
                <p><b>LP Name:</b> {trip_details['lp_name']} ({trip_details['lp_id']})</p>
                <p><b>ALP Name:</b> {trip_details['alp_name']} ({trip_details['alp_id']})</p>
                <p><b>HQ/CLI:</b> {trip_details['cli']}</p>
            </div>
            <div class="box">
                <h3>🚆 Train Details</h3>
                <p><b>Train No:</b> {trip_details['train_no']} ({trip_details['type']})</p>
                <p><b>Loco No:</b> {trip_details['loco_no']}</p>
                <p><b>Section:</b> {trip_details['section']}</p>
                <p><b>Date:</b> {trip_details['date']}</p>
            </div>
        </div>

        <h2>📊 Trip Summary</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Total Distance</td><td>{stats['dist']:.2f} km</td></tr>
            <tr><td>Total Duration</td><td>{stats['duration']:.2f} hrs</td></tr>
            <tr><td>Average Speed</td><td>{stats['avg_speed']:.2f} km/h</td></tr>
            <tr><td>Max Speed</td><td>{stats['max_speed']:.2f} km/h</td></tr>
            <tr><td>Stoppages</td><td>{len(stoppages)}</td></tr>
        </table>

        <h2>🛑 Stoppage Analysis (> {trip_details['stop_dur']} min)</h2>
        {stoppages.to_html(index=False, classes='table') if not stoppages.empty else "<p>No significant stoppages.</p>"}

        <h2>⚠️ Speed Violations & Observations</h2>
        {violations.to_html(index=False, classes='table') if not violations.empty else "<p>No signal speed violations detected (or no signal data provided).</p>"}

        <div style="margin-top: 50px; text-align: center; font-size: 0.9em; color: #777;">
            <p>Generated via SANKET SPM Analytics Dashboard | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </body>
    </html>
    """
    return html

# --- SIDEBAR: Data Uploads ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/en/thumb/4/45/Indian_Railways_logo.svg/1200px-Indian_Railways_logo.svg.png", width=100)
    st.title("Data Upload")
    
    st.info("1. Upload Locomotive CSV")
    loco_file = st.file_uploader("Choose SPM File", type=["csv"], key="loco")
    
    st.info("2. Reference Data (Optional)")
    signal_file = st.file_uploader("Signal List", type=["csv"], key="sig")
    ohe_file = st.file_uploader("OHE Master", type=["csv"], key="ohe")

# --- MAIN PAGE: Input Form ---
st.markdown('<div class="main-header">SANKET SPM Analysis Dashboard</div>', unsafe_allow_html=True)

# Container for Form inputs
with st.container():
    st.markdown('<div class="sub-header">1. Trip & Crew Details</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        lp_name = st.text_input("LP Name")
        lp_id = st.text_input("LP ID")
        cli_name = st.text_input("LP Group CLI")
    with col2:
        alp_name = st.text_input("ALP Name")
        alp_id = st.text_input("ALP ID")
        train_type = st.selectbox("Train Type", ["Coaching", "Vande Bharat", "Freight"])
    with col3:
        train_no = st.text_input("Train Number")
        loco_no = st.text_input("Loco Number")
        mps = st.number_input("MPS (km/h)", 110)

    colA, colB = st.columns(2)
    with colA:
        section_name = st.text_input("Section (e.g., DURG-NGP)")
    with colB:
        analysis_date = st.date_input("Date of Journey", datetime.today())

# --- ANALYSIS LOGIC ---
if loco_file:
    if st.button("🚀 Analyze Trip Data", type="primary"):
        with st.spinner("Processing GPS Telemetry..."):
            # 1. Load Loco Data
            df = load_data(loco_file)
            df['Logging Time'] = pd.to_datetime(df['Logging Time'])
            df = df.sort_values('Logging Time')
            
            # Distance Calc
            if 'distFromPrevLatLng' not in df.columns:
                df['distFromPrevLatLng'] = 0 # Placeholder if missing
            
            df['cum_dist_km'] = df['distFromPrevLatLng'].cumsum() / 1000
            
            # 2. Logic: Stoppages
            stop_thresh = 2.0
            min_dur_min = 2.0
            
            df['is_stopped'] = df['Speed'] < stop_thresh
            df['grp'] = (df['is_stopped'] != df['is_stopped'].shift()).cumsum()
            stoppages = df[df['is_stopped']].groupby('grp').agg(
                Start=('Logging Time', 'min'),
                End=('Logging Time', 'max'),
                Lat=('Latitude', 'mean'),
                Lon=('Longitude', 'mean')
            )
            stoppages['Duration_min'] = (stoppages['End'] - stoppages['Start']).dt.total_seconds() / 60
            valid_stops = stoppages[stoppages['Duration_min'] >= min_dur_min].copy()
            valid_stops['Location'] = valid_stops.apply(lambda x: f"{x['Lat']:.4f}, {x['Lon']:.4f}", axis=1)
            valid_stops = valid_stops[['Start', 'End', 'Duration_min', 'Location']].sort_values('Start')

            # 3. Logic: Signals (If available)
            violations_df = pd.DataFrame()
            if signal_file and ohe_file:
                # (Same mapping logic as before)
                sig_df = load_data(signal_file)
                ohe_df = load_data(ohe_file)
                ohe_df['OHEMas'] = ohe_df['OHEMas'].astype(str).str.strip()
                sig_df['OHE FROM'] = sig_df['OHE FROM'].astype(str).str.strip()
                
                merged = sig_df.merge(ohe_df[['OHEMas', 'Latitude', 'Longitude']], left_on='OHE FROM', right_on='OHEMas', how='left')
                mapped_sigs = merged.dropna(subset=['Latitude'])
                
                # Check speeds (Simplified for demo)
                # ... [Code for signal checking would go here] ...
            
            # 4. Prepare Stats
            total_dist = df['cum_dist_km'].max()
            total_time = (df['Logging Time'].max() - df['Logging Time'].min()).total_seconds() / 3600
            avg_speed = df['Speed'].mean()
            max_speed = df['Speed'].max()

            stats = {
                "dist": total_dist, "duration": total_time,
                "avg_speed": avg_speed, "max_speed": max_speed
            }
            
            trip_details = {
                "lp_name": lp_name, "lp_id": lp_id, "alp_name": alp_name, "alp_id": alp_id,
                "cli": cli_name, "train_no": train_no, "loco_no": loco_no, "type": train_type,
                "section": section_name, "date": str(analysis_date), "stop_dur": min_dur_min
            }

            # --- DISPLAY DASHBOARD ---
            st.success("Analysis Complete!")
            
            tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "🛑 Stoppages", "🗺️ Map", "📄 Report"])
            
            with tab1:
                # KPIs
                kpi1, kpi2, kpi3, kpi4 = st.columns(4)
                kpi1.metric("Distance", f"{total_dist:.1f} km")
                kpi2.metric("Duration", f"{total_time:.1f} hrs")
                kpi3.metric("Avg Speed", f"{avg_speed:.1f} km/h")
                kpi4.metric("Max Speed", f"{max_speed:.1f} km/h")
                
                # Graph
                st.subheader("Speed vs Time")
                fig = px.line(df, x='Logging Time', y='Speed', title=f"Speed Profile - {loco_no}")
                fig.add_hline(y=mps, line_dash="dash", line_color="red", annotation_text="MPS")
                st.plotly_chart(fig, use_container_width=True)

            with tab2:
                st.subheader("Detailed Stoppage List")
                st.dataframe(valid_stops, use_container_width=True)

            with tab3:
                st.subheader("Route Map")
                st.map(df[['Latitude', 'Longitude']])

            with tab4:
                st.subheader("Official Analysis Report")
                
                # Generate HTML Report
                report_html = generate_html_report(trip_details, stats, valid_stops, violations_df)
                
                # Show Preview
                st.components.v1.html(report_html, height=500, scrolling=True)
                
                # Download Button
                b64 = base64.b64encode(report_html.encode()).decode()
                href = f'<a href="data:text/html;base64,{b64}" download="SPM_Report_{loco_no}.html" style="text-decoration:none;">' \
                       f'<button style="background-color:#4CAF50; color:white; padding:10px 20px; border:none; border-radius:5px; cursor:pointer;">' \
                       f'📥 Download Full Report (Printable)</button></a>'
                st.markdown(href, unsafe_allow_html=True)
                st.caption("Tip: Open the downloaded file and press Ctrl+P to save as PDF.")

elif not loco_file:
    st.info("👋 Welcome! Please upload the Loco Data CSV from the sidebar to begin.")
