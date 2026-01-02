import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta
import base64

# --- Configuration & Setup ---
st.set_page_config(page_title="Railway SPM Analytics", layout="wide")

st.title("🚄 Locomotive SPM & Driving Behaviour Analytics")
st.markdown("Analyze GPS speedometer data, detect signal violations, and generate operational reports.")

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
    df = pd.read_csv(file)
    return df

# --- Sidebar Inputs ---
with st.sidebar:
    st.header("1. Upload Data")
    loco_file = st.file_uploader("Loco GPS Data (CSV)", type=["csv"])
    signal_file = st.file_uploader("Signal List (CSV)", type=["csv"])
    ohe_file = st.file_uploader("OHE Master (CSV)", type=["csv"])
    
    st.header("2. Operational Parameters")
    mps = st.number_input("Max Permissible Speed (km/h)", 110, 160, 110)
    train_type = st.selectbox("Train Type", ["Coaching", "Vande Bharat", "Freight"])
    
    st.header("3. Analysis Settings")
    stop_thresh = st.number_input("Stoppage Speed Threshold (km/h)", 0.0, 5.0, 2.0)
    stop_dur = st.number_input("Min Stoppage Duration (min)", 1, 60, 2)

# --- Main Analysis Logic ---
if loco_file:
    # 1. Process Loco Data
    loco_df = load_data(loco_file)
    loco_df['Logging Time'] = pd.to_datetime(loco_df['Logging Time'])
    loco_df = loco_df.sort_values('Logging Time')
    
    # Calculate cumulative distance if missing
    if 'distFromPrevLatLng' in loco_df.columns:
        loco_df['Distance_km'] = loco_df['distFromPrevLatLng'].cumsum() / 1000
    else:
        # Fallback if column missing (simple haversine step)
        loco_df['Distance_km'] = np.arange(len(loco_df)) * 0.01 # Dummy fallback

    # 2. Process Reference Data (if provided)
    signals_mapped = pd.DataFrame()
    if signal_file and ohe_file:
        try:
            sig_df = load_data(signal_file)
            ohe_df = load_data(ohe_file)
            
            # Clean and Merge
            ohe_df['OHEMas'] = ohe_df['OHEMas'].astype(str).str.strip()
            sig_df['OHE FROM'] = sig_df['OHE FROM'].astype(str).str.strip()
            
            merged = sig_df.merge(ohe_df[['OHEMas', 'Latitude', 'Longitude']], 
                                  left_on='OHE FROM', right_on='OHEMas', how='left')
            signals_mapped = merged.dropna(subset=['Latitude', 'Longitude'])
            st.success(f"Successfully mapped {len(signals_mapped)} signals.")
        except Exception as e:
            st.error(f"Error mapping signals: {e}")

    # --- Dashboard Layout ---
    
    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    total_dist = loco_df['Distance_km'].max()
    avg_spd = loco_df['Speed'].mean()
    max_spd = loco_df['Speed'].max()
    duration = (loco_df['Logging Time'].max() - loco_df['Logging Time'].min()).total_seconds() / 3600
    
    col1.metric("Total Distance", f"{total_dist:.2f} km")
    col2.metric("Avg Speed", f"{avg_spd:.2f} km/h")
    col3.metric("Max Speed", f"{max_spd:.2f} km/h")
    col4.metric("Duration", f"{duration:.2f} hrs")

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Speed Analysis", "🛑 Stoppages", "🚦 Signal Checks", "📝 Report"])

    with tab1:
        st.subheader("Speed Profile")
        fig = px.line(loco_df, x='Logging Time', y='Speed', title='Speed vs Time')
        # Add threshold line
        fig.add_hline(y=mps, line_dash="dash", line_color="red", annotation_text="MPS")
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("Section-wise Summary")
        if 'last/cur stationCode' in loco_df.columns:
            loco_df['section_grp'] = (loco_df['last/cur stationCode'] != loco_df['last/cur stationCode'].shift()).cumsum()
            sect_stats = loco_df.groupby(['section_grp', 'last/cur stationCode']).agg(
                Start=('Logging Time', 'min'),
                End=('Logging Time', 'max'),
                Avg_Speed=('Speed', 'mean'),
                Max_Speed=('Speed', 'max')
            ).reset_index()
            st.dataframe(sect_stats)
        else:
            st.warning("Station codes not found in data.")

    with tab2:
        st.subheader("Stoppage Analysis")
        loco_df['is_stopped'] = loco_df['Speed'] < stop_thresh
        loco_df['stop_grp'] = (loco_df['is_stopped'] != loco_df['is_stopped'].shift()).cumsum()
        
        stops = loco_df[loco_df['is_stopped']].groupby('stop_grp').agg(
            StartTime=('Logging Time', 'min'),
            EndTime=('Logging Time', 'max'),
            Lat=('Latitude', 'mean'),
            Lon=('Longitude', 'mean')
        )
        stops['Duration_min'] = (stops['EndTime'] - stops['StartTime']).dt.total_seconds() / 60
        valid_stops = stops[stops['Duration_min'] >= stop_dur].sort_values('Duration_min', ascending=False)
        
        st.dataframe(valid_stops)
        
        # Plot Stoppage Locations
        st.map(valid_stops[['Lat', 'Lon']].rename(columns={'Lat':'lat', 'Lon':'lon'}))

    with tab3:
        st.subheader("Signal Proximity & Speed Check")
        if not signals_mapped.empty:
            # Logic to find speed at signals
            results = []
            for _, sig in signals_mapped.iterrows():
                # Filter data near signal to speed up
                nearby = loco_df[
                    (loco_df['Latitude'].between(sig['Latitude']-0.01, sig['Latitude']+0.01)) &
                    (loco_df['Longitude'].between(sig['Longitude']-0.01, sig['Longitude']+0.01))
                ]
                if not nearby.empty:
                    # Find closest point
                    nearby['dist'] = haversine_vectorized(nearby['Latitude'], nearby['Longitude'], sig['Latitude'], sig['Longitude'])
                    closest = nearby.loc[nearby['dist'].idxmin()]
                    
                    if closest['dist'] < 200: # within 200m
                        results.append({
                            'Signal': sig['SIGNAL NAME'],
                            'Pass Time': closest['Logging Time'],
                            'Speed': closest['Speed'],
                            'Distance to Signal': closest['dist']
                        })
            
            if results:
                sig_res_df = pd.DataFrame(results)
                st.dataframe(sig_res_df)
                
                # Violation check (Naive: Check against Single Yellow limit as warning)
                limit = 60 if train_type == "Coaching" else 40
                violations = sig_res_df[sig_res_df['Speed'] > limit]
                if not violations.empty:
                    st.warning(f"Found {len(violations)} signals passed > {limit} km/h (Potential Yellow Violations)")
                    st.dataframe(violations)
                else:
                    st.success("No high-speed signal passes detected.")
            else:
                st.info("No GPS points matched close to provided Signal coordinates.")
        else:
            st.info("Please upload Signal and OHE Master files to enable this feature.")

    with tab4:
        st.subheader("Download Report")
        # Simple HTML Report Generation
        report_html = f"""
        <h1>SPM Analysis Report</h1>
        <p><b>Train:</b> {train_type} | <b>MPS:</b> {mps}</p>
        <h3>Summary</h3>
        <ul>
            <li>Distance: {total_dist:.2f} km</li>
            <li>Avg Speed: {avg_spd:.2f} km/h</li>
            <li>Max Speed: {max_spd:.2f} km/h</li>
        </ul>
        <h3>Stoppages</h3>
        {valid_stops.to_html()}
        """
        b64 = base64.b64encode(report_html.encode()).decode()
        href = f'<a href="data:text/html;base64,{b64}" download="SPM_Report.html">Download HTML Report</a>'
        st.markdown(href, unsafe_allow_html=True)

else:
    st.info("Awaiting Data Upload...")
