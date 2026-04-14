import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px
import io

st.set_page_config(page_title="Digital Village Project", page_icon="🌾", layout="wide")

@st.cache_resource
def get_engine():
    host = st.secrets["DB_HOST"]
    name = st.secrets["DB_NAME"]
    user = st.secrets["DB_USER"]
    pwd  = st.secrets["DB_PASS"]
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

all_cols = [c for c in ['Farmer Name', 'Village', 'Phone', 'Age',
            'Acres', 'Ownership', 'Method', 'Enumerator',
            'Date', 'Submitted At'] if c in filtered.columns]

d1, d2 = st.columns([2, 1])

with d1:
    selected_cols = st.multiselect(
        "Select columns to include in download:",
        options=all_cols,
        default=all_cols
    )

with d2:
    fmt = st.selectbox("Format:", ["CSV", "Excel", "JSON"])

if selected_cols:
    export_df = filtered[selected_cols].copy()
    export_df = export_df.reset_index()
    if 'Phone' in export_df.columns:
        export_df['Phone'] = export_df['Phone'].astype(str)

    if fmt == "CSV":
        data = export_df.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Download", data=data,
                           file_name="farms.csv", mime="text/csv")
    elif fmt == "Excel":
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w:
            export_df.to_excel(w, index=False, sheet_name='Farms')
        st.download_button("⬇️ Download", data=buf.getvalue(),
                           file_name="farms.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    elif fmt == "JSON":
        data = export_df.to_json(orient='records', indent=2).encode('utf-8')
        st.download_button("⬇️ Download", data=data,
                           file_name="farms.json", mime="application/json")

st.caption("Data refreshes every 60 seconds from AWS database.")
