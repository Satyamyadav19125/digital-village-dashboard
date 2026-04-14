import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px

# ── Page config ──────────────────────────────────────
st.set_page_config(
    page_title="Digital Village Project",
    page_icon="🌾",
    layout="wide"
)

# ── Database connection ───────────────────────────────
@st.cache_resource
def get_engine():
    host = st.secrets["DB_HOST"]
    name = st.secrets["DB_NAME"]
    user = st.secrets["DB_USER"]
    pwd  = st.secrets["DB_PASS"]
    return create_engine(
        f"postgresql://{user}:{pwd}@{host}:5432/{name}"
    )

@st.cache_data(ttl=60)
def load_data():
    engine = get_engine()
    df = pd.read_sql('SELECT * FROM farm_registrations', engine)
    return df

# ── Load data ─────────────────────────────────────────
df = load_data()

# ── Rename key columns for display ───────────────────
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
    'Consent/Studyagree':            'Study Agreement',
    'Consent/TPR_DSR':               'Method',
    '_submission_time':              'Submitted At',
    '_id':                           'ID'
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
col3.metric("Blocks", df['inthebeginning/Village'].nunique() if 'inthebeginning/Village' in df else "—")
col4.metric("Latest Submission", str(df_display['Submitted At'].max())[:10] if 'Submitted At' in df_display else "—")

st.markdown("---")

# ── Charts row ────────────────────────────────────────
st.subheader("📊 Overview Charts")
c1, c2 = st.columns(2)

with c1:
    if 'Village' in df_display:
        village_counts = df_display['Village'].value_counts().reset_index()
        village_counts.columns = ['Village', 'Count']
        fig1 = px.bar(
            village_counts.head(15),
            x='Count', y='Village',
            orientation='h',
            title='Top 15 Villages by Farm Count',
            color='Count',
            color_continuous_scale='Blues'
        )
        fig1.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig1, use_container_width=True)

with c2:
    if 'Method' in df_display:
        method_counts = df_display['Method'].value_counts().reset_index()
        method_counts.columns = ['Method', 'Count']
        fig2 = px.pie(
            method_counts,
            values='Count',
            names='Method',
            title='TPR vs DSR Distribution',
            color_discrete_sequence=px.colors.sequential.Blues
        )
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

# ── Apply filters ─────────────────────────────────────
filtered = df_display.copy()

if selected_village != 'All' and 'Village' in filtered.columns:
    filtered = filtered[filtered['Village'] == selected_village]

if search_name and 'Farmer Name' in filtered.columns:
    filtered = filtered[filtered['Farmer Name'].str.contains(search_name, case=False, na=False)]

if search_phone and 'Phone' in filtered.columns:
    filtered = filtered[filtered['Phone'].astype(str).str.contains(search_phone, na=False)]

st.caption(f"Showing {len(filtered)} of {len(df_display)} records")

# ── Data table ────────────────────────────────────────
st.subheader("📋 Farm Registrations")

display_cols = [c for c in ['ID', 'Farmer Name', 'Village', 'Phone', 'Age',
                              'Acres', 'Ownership', 'Method', 'Enumerator',
                              'Date', 'Submitted At'] if c in filtered.columns]

st.dataframe(
    filtered[display_cols].sort_values('Submitted At', ascending=False) if 'Submitted At' in filtered.columns else filtered[display_cols],
    use_container_width=True,
    height=400
)

# ── Export ────────────────────────────────────────────
st.markdown("---")

# Fix formatting before export
export_df = filtered[display_cols].copy()
if 'ID' in export_df.columns:
    export_df['ID'] = export_df['ID'].astype(str)
if 'Phone' in export_df.columns:
    export_df['Phone'] = export_df['Phone'].astype(str)

csv = export_df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="⬇️ Download filtered data as CSV",
    data=csv,
    file_name="farm_registrations.csv",
    mime="text/csv"
)

st.caption("Data refreshes every 60 seconds from AWS database.")
