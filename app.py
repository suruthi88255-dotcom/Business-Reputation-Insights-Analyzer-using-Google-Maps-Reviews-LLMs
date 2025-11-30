import streamlit as st
import pandas as pd
import plotly.express as px
import os
import data_fetcher
import analyzer

st.set_page_config(page_title="Review Intelligence AI", layout="wide")
DATA_FILE = "data/reviews_analyzed.csv"

# --- INITIALIZE SESSION STATE ---
if 'last_query' not in st.session_state:
    st.session_state.last_query = ""
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
if 'final_data_path' not in st.session_state:
    st.session_state.final_data_path = ""

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .big-font { font-size:20px !important; }
    .metric-box {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# --- TITLE & SEARCH ---
st.title("🤖 AI Business Reputation Analyzer")
st.markdown("Enter a business name to fetch reviews, analyze sentiment, and get AI recommendations.")

col1, col2 = st.columns([3, 1])
with col1:
    query = st.text_input("📍 Enter Business Name & City (e.g., 'TCS Chennai')", "")
with col2:
    st.write("") # Spacer
    st.write("") # Spacer
    search_btn = st.button("🚀 Analyze Reviews", type="primary", use_container_width=True)

# --- MAIN LOGIC ---
if search_btn and query:
    
    # Define unique file names based on the query
    # The Scraper ensures the raw file is current, and we define a unique analyzed file path
    raw_file_name = data_fetcher.get_clean_filename(query)
    # The analyzer is configured to read the generic reviews_raw.csv and write to a generic reviews_analyzed.csv.
    # To keep the Streamlit display simple, we rely on the analyzer overwriting the generic file path:
    analyzed_file_name = DATA_FILE
    
    # Reset state for a fresh run
    st.session_state.last_query = query
    st.session_state.data_loaded = False 
    st.session_state.final_data_path = analyzed_file_name # Set the expected output path
    
    # 1. DATA FETCHING & ANALYSIS PHASE
    with st.status(f"🕵️‍♂️ Analyzing '{query}'...", expanded=True) as status:
        
        st.write("🌐 Connecting to Google Maps...")
        # Calls data_fetcher.py to scrape data
        data_fetcher.run_scraper(query) 
        st.write("✅ Reviews fetched successfully!")
        
        st.write("🧠 Sending data to AI Brain (Hugging Face)...")
        # Calls analyzer.py to process data (It reads reviews_raw.csv and writes reviews_analyzed.csv)
        analyzer.analyze_reviews() 
        st.write("✅ Sentiment analysis complete!")
        
        # Final check if the analyzer successfully created the file
        if os.path.exists(DATA_FILE) and pd.read_csv(DATA_FILE).shape[0] > 0:
            st.session_state.data_loaded = True
            status.update(label="All processes complete!", state="complete", expanded=False)
        else:
            status.update(label="Analysis failed or returned no data. Check console for details.", state="error", expanded=False)

    # Force a rerun to reload the new CSV data and display the dashboard
    st.rerun()

# --- DASHBOARD DISPLAY ---
# Display components only if the process was successful and the file exists
if st.session_state.data_loaded and os.path.exists(DATA_FILE):
    
    try:
        # Load the newly processed data
        df = pd.read_csv(DATA_FILE)
    except Exception as e:
        st.error(f"Error reading final data: {e}. Check console for details.")
        st.stop()
    
    # Ensure the dataframe is valid before plotting
    if df.empty or df.shape[0] == 0:
        st.error("❌ Analysis returned an empty dataset. Try a different query.")
        st.session_state.data_loaded = False
        st.stop()

    st.divider()
    st.success(f"Displaying Results for: **{st.session_state.last_query.upper()}**")
    st.divider()
    
    # SECTION A: METRICS
    st.subheader("📊 Executive Summary")
    
    # Calculate Metrics
    total_reviews = len(df)
    avg_rating = df['rating'].mean()
    
    # Robust Sentiment Calculation
    if 'sentiment' in df.columns:
        pos_count = len(df[df['sentiment'].str.contains("Positive", case=False, na=False)])
        pos_pct = (pos_count / total_reviews) * 100
    else:
        pos_pct = 0

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Reviews Analyzed", total_reviews)
    m2.metric("Average Rating", f"{avg_rating:.1f} ⭐")
    m3.metric("Customer Satisfaction", f"{pos_pct:.1f}%")

    st.divider()

    # SECTION B: VISUALIZATIONS
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("Sentiment Split")
        if 'sentiment' in df.columns:
            # Create Pie Chart
            fig_pie = px.pie(df, names='sentiment', color='sentiment',
                             color_discrete_map={'Positive':'green', 'Negative':'red', 'Neutral':'gray'},
                             hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.warning("Sentiment data not available yet.")
    
    with c2:
        st.subheader("Rating Distribution")
        # Create Bar Chart
        fig_bar = px.bar(df['rating'].value_counts().reset_index(), 
                         x='rating', y='count', 
                         labels={'rating':'Stars', 'count':'Review Count'},
                         color_discrete_sequence=['#3366cc'])
        st.plotly_chart(fig_bar, use_container_width=True)

    # SECTION C & D: RECOMMENDATIONS AND TABLE
    st.divider()
    st.subheader("💡 AI Strategic Recommendations")
    
    if 'recommendation' in df.columns:
        recs = df['recommendation'].dropna().unique()
        count = 0
        for rec in recs:
            if len(str(rec)) > 10: 
                st.info(f"**Insight {count+1}:** {rec}")
                count += 1
                if count >= 5: break
    
    with st.expander("📝 View All Analyzed Reviews"):
        desired_cols = ['author', 'rating', 'sentiment', 'summary', 'text']
        valid_cols = [c for c in desired_cols if c in df.columns]
        
        if valid_cols:
            st.dataframe(df[valid_cols], use_container_width=True)
        else:
            st.dataframe(df, use_container_width=True)

elif search_btn and not query:
    st.warning("Please enter a business name to start the analysis.")