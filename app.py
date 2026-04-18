import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px
import io

st.set_page_config(page_title="Digital Village Project", page_icon="🌾", layout="wide")

@st.cache_resource
def get_engine():
    import os
    host = os.environ.get("DB_HOST") or st.secrets.get("DB_HOST")
    name = os.environ.get("DB_NAME") or st.secrets.get("DB_NAME")
    user = os.environ.get("DB_USER") or st.secrets.get("DB_USER")
    pwd  = os.environ.get("DB_PASS") or st.secrets.get("DB_PASS")
    return create_engine(f"postgresql://{user}:{pwd}@{host}:5432/{name}")

@st.cache_data(ttl=60)
def load_data():
    engine = get_engine()
    df = pd.read_sql('SELECT * FROM farm_registrations', engine)
    return df

df = load_data()

col_map = {
    'inthebeginning/Village':        'Village',
    'inthebeginning/Enter_a_date':   'Date',
    'inthebeginning/Enter_your_name':'Enumerator',
    'Demography/Namefarmer':         'Farmer Name',
    'Demography/phnofarmer':         'Phone',
    'Demography/agefarmer':          'Age',
    'Demography/Education':          'Education',
    'Facres/Acres':                  'Acres',
    'Acerage/Own':                   'Ownership',
    'Consent/TPR_DSR':               'Method',
    '_submission_time':              'Submitted At',
}
df_display = df.rename(columns=col_map)

# ── Header ────────────────────────────────────────────
st.title("🌾 Digital Village Project")
st.markdown("**Tel Aviv University | Thapar University, Patiala**")
st.markdown("---")

# ── Summary cards ─────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Farms", len(df))
col2.metric("Villages", df_display['Village'].nunique() if 'Village' in df_display else "—")
col3.metric("Blocks", df_display['Village'].nunique() if 'Village' in df_display else "—")
col4.metric("Latest Submission", str(df_display['Submitted At'].max())[:10] if 'Submitted At' in df_display else "—")
st.markdown("---")

# ── Charts ────────────────────────────────────────────
st.subheader("📊 Overview Charts")
c1, c2 = st.columns(2)
with c1:
    if 'Village' in df_display:
        vc = df_display['Village'].value_counts().reset_index()
        vc.columns = ['Village', 'Count']
        fig1 = px.bar(vc.head(15), x='Count', y='Village', orientation='h',
                      title='Top 15 Villages by Farm Count', color='Count',
                      color_continuous_scale='Blues')
        fig1.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig1, use_container_width=True)
with c2:
    if 'Method' in df_display:
        mc = df_display['Method'].value_counts().reset_index()
        mc.columns = ['Method', 'Count']
        fig2 = px.pie(mc, values='Count', names='Method',
                      title='TPR vs DSR Distribution',
                      color_discrete_sequence=px.colors.sequential.Blues)
        fig2.update_layout(height=400)
        st.plotly_chart(fig2, use_container_width=True)
st.markdown("---")

# ── Filters ───────────────────────────────────────────
st.subheader("🔍 Filter & Search")
f1, f2, f3 = st.columns(3)
with f1:
    villages = ['All'] + sorted(df_display['Village'].dropna().unique().tolist()) if 'Village' in df_display else ['All']
    selected_village = st.selectbox("Filter by Village", villages)
with f2:
    search_name = st.text_input("Search by Farmer Name", "")
with f3:
    search_phone = st.text_input("Search by Phone Number", "")

filtered = df_display.copy()
if selected_village != 'All':
    filtered = filtered[filtered['Village'] == selected_village]
if search_name:
    filtered = filtered[filtered['Farmer Name'].str.contains(search_name, case=False, na=False)]
if search_phone:
    filtered = filtered[filtered['Phone'].astype(str).str.contains(search_phone, na=False)]

# Sort and add clean serial number
if 'Submitted At' in filtered.columns:
    filtered = filtered.sort_values('Submitted At', ascending=False)
filtered = filtered.reset_index(drop=True)
filtered.index = filtered.index + 1
filtered.index.name = 'No.'

st.caption(f"Showing {len(filtered)} of {len(df_display)} records")

# ── Data table ────────────────────────────────────────
st.subheader("📋 Farm Registrations")

display_cols = [c for c in ['Farmer Name', 'Village', 'Phone', 'Age',
                'Acres', 'Ownership', 'Method', 'Enumerator',
                'Date', 'Submitted At'] if c in filtered.columns]

st.dataframe(filtered[display_cols], use_container_width=True, height=400)
st.markdown("---")

# ── Download ──────────────────────────────────────────
st.subheader("⬇️ Download Data")

tab1, tab2 = st.tabs(["📋 Key Columns (11)", "📦 Full Data (All Columns)"])

with tab1:
    st.caption("Downloads: No., Farmer Name, Village, Phone, Age, Acres, Ownership, Method, Enumerator, Date, Submitted At")
    d1, d2 = st.columns([1, 1])
    with d1:
        fmt1 = st.selectbox("Format:", ["CSV", "Excel", "JSON"], key="fmt1")
    with d2:
        st.write("")
        export_key = filtered[display_cols].copy().reset_index()
        if 'Phone' in export_key.columns:
            export_key['Phone'] = export_key['Phone'].astype(str)
        if fmt1 == "CSV":
            st.download_button("⬇️ Download Key Columns",
                data=export_key.to_csv(index=False).encode('utf-8'),
                file_name="farms_key.csv", mime="text/csv")
        elif fmt1 == "Excel":
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                export_key.to_excel(w, index=False, sheet_name='Farms')
            st.download_button("⬇️ Download Key Columns",
                data=buf.getvalue(), file_name="farms_key.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        elif fmt1 == "JSON":
            st.download_button("⬇️ Download Key Columns",
                data=export_key.to_json(orient='records', indent=2).encode('utf-8'),
                file_name="farms_key.json", mime="application/json")

with tab2:
    st.caption("Downloads all 70+ columns including GPS, polygons, rice varieties, tubewell details, everything.")
    d3, d4 = st.columns([1, 1])
    with d3:
        fmt2 = st.selectbox("Format:", ["CSV", "Excel", "JSON"], key="fmt2")
    with d4:
        st.write("")
        export_full = filtered.copy().reset_index(drop=True)
        export_full.index = export_full.index + 1
        export_full.index.name = 'No.'
        export_full = export_full.reset_index()
        if 'Phone' in export_full.columns:
            export_full['Phone'] = export_full['Phone'].astype(str)
        if fmt2 == "CSV":
            st.download_button("⬇️ Download Full Data",
                data=export_full.to_csv(index=False).encode('utf-8'),
                file_name="farms_full.csv", mime="text/csv")
        elif fmt2 == "Excel":
            buf2 = io.BytesIO()
            with pd.ExcelWriter(buf2, engine='openpyxl') as w:
                export_full.to_excel(w, index=False, sheet_name='Full Data')
            st.download_button("⬇️ Download Full Data",
                data=buf2.getvalue(), file_name="farms_full.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        elif fmt2 == "JSON":
            st.download_button("⬇️ Download Full Data",
                data=export_full.to_json(orient='records', indent=2).encode('utf-8'),
                file_name="farms_full.json", mime="application/json")

st.caption("Data refreshes every 60 seconds from AWS database.")
