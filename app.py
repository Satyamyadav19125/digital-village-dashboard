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
    'Consent/Studyagree':            'Study Agreement',
    'Consent/TPR_DSR':               'Method',
    '_submission_time':              'Submitted At',
}
df_display = df.rename(columns=col_map)

# Add sequential row number
df_display.insert(0, 'No.', range(1, len(df_display) + 1))

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

st.caption(f"Showing {len(filtered)} of {len(df_display)} records")
st.markdown("---")

# ── Column selector ───────────────────────────────────
st.subheader("📋 Farm Registrations")

all_cols = ['No.', 'Farmer Name', 'Village', 'Phone', 'Age',
            'Acres', 'Ownership', 'Method', 'Enumerator', 'Date', 'Submitted At']
all_cols = [c for c in all_cols if c in filtered.columns]

st.markdown("**Select columns to show:**")
cols_per_row = 4
rows = [all_cols[i:i+cols_per_row] for i in range(0, len(all_cols), cols_per_row)]
selected_cols = []
for row in rows:
    check_cols = st.columns(len(row))
    for i, col_name in enumerate(row):
        if check_cols[i].checkbox(col_name, value=True, key=f"col_{col_name}"):
            selected_cols.append(col_name)

if not selected_cols:
    st.warning("Please select at least one column.")
    selected_cols = all_cols

# Show table
show_df = filtered[selected_cols]
if 'Submitted At' in show_df.columns:
    show_df = show_df.sort_values('Submitted At', ascending=False)

st.dataframe(show_df, use_container_width=True, height=400)
st.markdown("---")

# ── Export ────────────────────────────────────────────
st.subheader("⬇️ Download Data")

# Format columns for export
export_df = show_df.copy()
if 'Phone' in export_df.columns:
    export_df['Phone'] = export_df['Phone'].astype(str)

col_fmt, col_btn = st.columns([1, 2])

with col_fmt:
    fmt = st.selectbox("Select export format:", ["CSV", "Excel (XLS)", "JSON"])

with col_btn:
    st.write("")
    st.write("")
    if fmt == "CSV":
        csv = export_df.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Download CSV", data=csv,
                           file_name="farm_registrations.csv", mime="text/csv")

    elif fmt == "Excel (XLS)":
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            export_df.to_excel(writer, index=False, sheet_name='Farm Registrations')
        st.download_button("⬇️ Download Excel", data=buffer.getvalue(),
                           file_name="farm_registrations.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    elif fmt == "JSON":
        json_data = export_df.to_json(orient='records', indent=2).encode('utf-8')
        st.download_button("⬇️ Download JSON", data=json_data,
                           file_name="farm_registrations.json", mime="application/json")

st.caption("Data refreshes every 60 seconds from AWS database.")
