import streamlit as st
import pandas as pd
import json

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Guest reviews",
    page_icon="hb",
    layout="wide"
)

# -----------------------------------------------------------------------------
# 2. CSS STYLING
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=BlinkMacSystemFont:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    /* Main Score Badge */
    .booking-badge {
        background-color: #003580;
        color: white;
        padding: 8px 14px;
        border-radius: 8px 8px 8px 0px;
        font-weight: 700;
        font-size: 24px;
        display: inline-block;
        margin-right: 12px;
    }

    .cat-name { 
        font-weight: 600; 
        font-size: 15px; 
        color: #1a1a1a;
        white-space: nowrap;
    }

    .cat-pred-score { 
        font-weight: 700; 
        font-size: 15px; 
        color: #6B5115; 
    }

    .rev-count { 
        color: #6b6b6b; 
        font-size: 12px; 
        font-weight: 400;
        white-space: nowrap;
    }

    .booking-official-score { 
        font-weight: 700; 
        font-size: 15px; 
        color: #1a1a1a;
        text-align: right;
    }

    .progress-bg { 
        background-color: #e9ecef; 
        border-radius: 4px; 
        height: 10px; 
        width: 100%; 
        margin-top: 6px;
    }
    .bar-blue { background-color: #003580; height: 100%; border-radius: 4px; }
    .bar-green { background-color: #008009; height: 100%; border-radius: 4px; }

    /* --- TOOLTIP STYLE --- */
    .tooltip {
        position: relative;
        display: inline-block;
        cursor: help;
        color: #6b6b6b;
        font-size: 18px;
        line-height: 1;
    }
    .tooltip:hover { color: #003580; }
    .tooltip .tooltiptext {
        visibility: hidden;
        width: 280px;
        background-color: #fff;
        color: #333;
        border-radius: 8px;
        padding: 12px;
        position: absolute;
        z-index: 999;
        bottom: 140%; 
        left: 50%;
        margin-left: -140px; 
        box-shadow: 0px 4px 15px rgba(0,0,0,0.2);
        border: 1px solid #e0e0e0;
        font-size: 13px;
        opacity: 0;
        transition: opacity 0.2s;
        white-space: normal;
    }
    .tooltip:hover .tooltiptext { visibility: visible; opacity: 1; }
    .tooltip-review {
        border-left: 3px solid #6A1B9A;
        padding-left: 8px;
        margin-bottom: 8px;
        font-style: italic;
        font-family: 'Georgia', serif;
        display: block;
    }
    .tooltip-header { font-weight: 700; margin-bottom: 8px; display: block; border-bottom: 1px solid #eee; }

    /* Utility */
    div[data-testid="column"] { padding: 0px !important; }
    .row-spacer { height: 35px; }
</style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# 3. DATA LOADING
# -----------------------------------------------------------------------------
@st.cache_data
def load_and_merge_data():
    try:
        real_df = pd.read_csv("scraped_booking_real_scores.csv")
        pred_df = pd.read_csv("tool_input.csv")
        if 'Staff' in real_df.columns:
            real_df = real_df[real_df['Staff'] > 0]
        real_df['clean_key'] = real_df['HotelName'].astype(str).str.lower().str.strip()
        real_df = real_df.drop_duplicates(subset=['clean_key'], keep='first')
        pred_df['clean_key'] = pred_df['hotel_id'].astype(str).apply(lambda x: x.split(',')[0].lower().strip())
        return pd.merge(pred_df, real_df, on='clean_key', how='inner')
    except Exception:
        return None


df = load_and_merge_data()

# -----------------------------------------------------------------------------
# 4. UI LOGIC
# -----------------------------------------------------------------------------
st.write("## Guest reviews")

if df is None:
    st.error("⚠️ Data Error.")
    st.stop()

search_query = st.text_input("Search for a hotel...", placeholder="Type name...").strip()
matches = df[df['hotel_id'].str.contains(search_query, case=False, na=False)] if search_query else df

if not matches.empty:
    hotel_list = matches['hotel_id'].tolist()
    selected_hotel_id = st.selectbox("Select Hotel:", hotel_list, label_visibility="collapsed")
    row = matches[matches['hotel_id'] == selected_hotel_id].iloc[0]

    try:
        pred_categories = json.loads(row['hotel_categories_score'])
    except:
        pred_categories = {}

    avg_real = sum([row[c] for c in ['Staff', 'Facilities', 'Cleanliness', 'Comfort', 'Location'] if c in row]) / 5

    # Header
    c1, c2 = st.columns([1, 12])
    with c1:
        st.markdown(f'<div class="booking-badge">{avg_real:.1f}</div>', unsafe_allow_html=True)
    with c2:
        st.markdown("<div style='font-size: 16px; margin-top: 5px;'><b>Exceptional</b> · 2,086 reviews</div>",
                    unsafe_allow_html=True)

    st.write("---")
    st.write("### Categories")

    target_cats = ['staff', 'facilities', 'cleanliness', 'comfort', 'location', 'free_wifi']

    for i in range(0, len(target_cats), 3):
        cols = st.columns(3, gap="large")
        for j in range(3):
            if i + j < len(target_cats):
                cat_key = target_cats[i + j]
                real_score = row.get(cat_key.title(), 0.0)
                label = "Free WiFi" if cat_key == 'free_wifi' else cat_key.title()

                has_pred = cat_key in pred_categories

                with cols[j]:
                    # --- THE 5-COLUMN SPLIT ---
                    # 1: Label, 2: Pred Score, 3: Icon, 4: Review Count, 5: Real Score
                    c_label, c_pred_score, c_icon, c_text, c_real = st.columns([1.3, 0.7, 0.4, 3.0, 1.0])

                    with c_label:
                        st.markdown(f'<span class="cat-name">{label}</span>', unsafe_allow_html=True)

                    if has_pred:
                        pred_data = pred_categories[cat_key]
                        pred_val_str = "{:.2f}".format(float(pred_data.get('score', 0)))
                        count = pred_data.get('number_reviews', 0)
                        pred_examples = pred_data.get('examples', [])

                        reviews_html = "".join(
                            [f'<span class="tooltip-review">“{r.replace("\"", "&quot;")}”</span>' for r in
                             pred_examples[:3]])
                        tooltip_html = f'<div class="tooltip">ⓘ<span class="tooltiptext"><span class="tooltip-header">Predicted Reviews:</span>{reviews_html}</span></div>'

                        with c_pred_score:
                            st.markdown(f'<span class="cat-pred-score">{pred_val_str}</span>', unsafe_allow_html=True)
                        with c_icon:
                            st.markdown(tooltip_html, unsafe_allow_html=True)
                        with c_text:
                            st.markdown(f'<span class="rev-count">(based on {count} reviews)</span>',
                                        unsafe_allow_html=True)

                    with c_real:
                        st.markdown(f'<div class="booking-official-score">{real_score}</div>', unsafe_allow_html=True)

                    # Progress Bar
                    bar_class = "bar-green" if cat_key in ['cleanliness', 'comfort'] else "bar-blue"
                    st.markdown(
                        f'<div class="progress-bg"><div class="{bar_class}" style="width: {real_score * 10}%;"></div></div>',
                        unsafe_allow_html=True)

        st.markdown('<div class="row-spacer"></div>', unsafe_allow_html=True)

elif search_query:
    st.warning("No hotels found.")