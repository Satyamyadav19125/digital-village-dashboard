import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px
import io
import folium
import math
import streamlit.components.v1 as components

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

def parse_polygon(poly_str):
    if not poly_str or str(poly_str) in ('None','nan'): return []
    pts = []
    for seg in str(poly_str).strip().split(';'):
        p = seg.strip().split()
        if len(p) >= 2:
            try: pts.append([float(p[0]), float(p[1])])
            except: pass
    return pts if len(pts) >= 3 else []

def parse_point(loc_str):
    if not loc_str or str(loc_str) in ('None','nan'): return None
    p = str(loc_str).strip().split()
    if len(p) >= 2:
        try: return [float(p[0]), float(p[1])]
        except: return None

def calc_area(coords):
    if len(coords) < 3: return None
    avg_lat = sum(c[0] for c in coords) / len(coords)
    lon_m = 111000 * math.cos(math.radians(avg_lat))
    pts = [(c[1]*lon_m, c[0]*111000) for c in coords]
    n, area = len(pts), 0
    for i in range(n):
        j = (i+1) % n
        area += pts[i][0]*pts[j][1] - pts[j][0]*pts[i][1]
    return round(abs(area)/2 * 0.000247105, 2)

def clean(val):
    s = str(val) if val is not None else ''
    return '—' if s in ('nan','None','') else s

def parse_pump(pump_str):
    if not pump_str or pump_str == '—': return '—', '—'
    try:
        raw = str(pump_str).lower()
        parts = raw.split()
        hp_part = next((p for p in parts if 'horsepower' in p or ('hp' in p and 'mm' not in p)), '')
        mm_part = next((p for p in parts if 'mm' in p), '')
        hp = hp_part.replace('_horsepower','').replace('horsepower','').replace('_hp_to_','_to_').replace('_hp','')
        hp = hp.replace('_to_',' to ').replace('_',' ').strip()
        hp = hp.replace('12 5','12.5').replace('17 5','17.5').replace('7 5','7.5').replace('22 5','22.5')
        mm = mm_part.replace('_width','').replace('width','').strip()
        return (hp or '—'), (mm or '—')
    except:
        return '—', '—'

df = load_data()
df_indexed = df.reset_index(drop=True)

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
df_display = df_indexed.rename(columns=col_map)

st.title("🌾 Digital Village Project")
st.markdown("**Tel Aviv University | Thapar University, Patiala**")
st.markdown("---")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Farms", len(df_indexed))
col2.metric("Villages", df_display['Village'].nunique() if 'Village' in df_display else "—")
col3.metric("Blocks", df_display['Village'].nunique() if 'Village' in df_display else "—")
col4.metric("Latest Submission", str(df_display['Submitted At'].max())[:10] if 'Submitted At' in df_display else "—")
st.markdown("---")

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
        mc_df = df_display['Method'].value_counts().reset_index()
        mc_df.columns = ['Method', 'Count']
        fig2 = px.pie(mc_df, values='Count', names='Method',
                      title='TPR vs DSR Distribution',
                      color_discrete_sequence=px.colors.sequential.Blues)
        fig2.update_layout(height=400)
        st.plotly_chart(fig2, use_container_width=True)
st.markdown("---")

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

if 'Submitted At' in filtered.columns:
    filtered = filtered.sort_values('Submitted At', ascending=False)

filtered['_orig_pos'] = filtered.index
filtered = filtered.reset_index(drop=True)
filtered.index = filtered.index + 1
filtered.index.name = 'No.'

st.caption(f"Showing {len(filtered)} of {len(df_display)} records")

st.subheader("📋 Farm Registrations")
st.caption("👆 Click any row to instantly view full farm profile below")

display_cols = [c for c in ['Farmer Name', 'Village', 'Phone', 'Age',
                'Acres', 'Ownership', 'Method', 'Enumerator',
                'Date', 'Submitted At'] if c in filtered.columns]

selected = st.dataframe(
    filtered[display_cols],
    use_container_width=True,
    height=400,
    on_select="rerun",
    selection_mode="single-row",
)

selected_rows = selected.selection.rows if selected.selection else []
if selected_rows:
    st.session_state['view_farmer_idx'] = selected_rows[0]
elif 'view_farmer_idx' in st.session_state:
    del st.session_state['view_farmer_idx']

if 'view_farmer_idx' in st.session_state:
    row_idx = st.session_state['view_farmer_idx']
    if row_idx < len(filtered):
        farmer_display = filtered.iloc[row_idx]
        farmer_name = clean(farmer_display.get('Farmer Name', 'Unknown'))
        orig_pos = int(farmer_display['_orig_pos'])
        raw_row = df_indexed.iloc[orig_pos]

        st.markdown("---")
        st.subheader(f"🌾 Farm Profile — {farmer_name}")

        i1, i2, i3, i4 = st.columns(4)
        i1.metric("Village", clean(farmer_display.get('Village','—')))
        i2.metric("Acres", clean(farmer_display.get('Acres','—')))
        i3.metric("Method", clean(farmer_display.get('Method','—')))
        i4.metric("Ownership", clean(farmer_display.get('Ownership','—')))

        left, right = st.columns([1, 1.5])

        with left:
            st.markdown("##### 👤 Farmer Details")
            for k, v in {
                "📞 Phone": clean(farmer_display.get('Phone','—')),
                "🎂 Age": clean(farmer_display.get('Age','—')),
                "🎓 Education": clean(farmer_display.get('Education','—')),
                "👷 Enumerator": clean(farmer_display.get('Enumerator','—')),
                "📅 Date": clean(farmer_display.get('Date','—')),
                "🕐 Submitted": clean(farmer_display.get('Submitted At','—')),
            }.items():
                if v != '—':
                    st.markdown(f"**{k}:** {v}")

            st.markdown("##### 🔧 Tubewell Details")
            hp1, mm1 = parse_pump(clean(raw_row.get('Tubewells/pump1','—')))
            hp2, mm2 = parse_pump(clean(raw_row.get('Tubewells/pump2','—')))
            for k, v in {
                "🔧 No. Tubewells": clean(raw_row.get('Tubewells/Tubewells_001','—')),
                "⚙️ Horsepower 1": hp1,
                "📏 Delivery MM 1": mm1,
                "📐 Bore Depth 1": clean(raw_row.get('Tubewells/BD1','—')) + " ft",
                "⚙️ Horsepower 2": hp2,
                "📏 Delivery MM 2": mm2,
                "📐 Bore Depth 2": clean(raw_row.get('Tubewells/BD2','—')) + " ft",
                "💦 Water Level": clean(raw_row.get('GWL_001/GWL','—')) + " ft",
                "🤝 Tube Share": clean(raw_row.get('GWL_001/Tubeshare','—')),
            }.items():
                if '—' not in v:
                    st.markdown(f"**{k}:** {v}")

        with right:
            st.markdown("##### 🗺️ Farm Location")

            name_r = clean(raw_row.get('Demography/Namefarmer'))
            phone_r = clean(raw_row.get('Demography/phnofarmer'))
            age_r = clean(raw_row.get('Demography/agefarmer'))
            acres_r = clean(raw_row.get('Facres/Acres'))
            village_r = clean(raw_row.get('inthebeginning/Village'))
            ownership_r = clean(raw_row.get('Acerage/Own'))
            method_r = clean(raw_row.get('Consent/TPR_DSR'))
            pump_r = clean(raw_row.get('Tubewells/pump1'))
            bd_r = clean(raw_row.get('Tubewells/BD1'))
            gwl_r = clean(raw_row.get('GWL_001/GWL'))
            hp_r, mm_r = parse_pump(pump_r)

            poly_str = raw_row.get('Poly1/map1') or raw_row.get('Poly2/map2') or raw_row.get('Poly3/map3')
            points = parse_polygon(poly_str)
            tw_loc = parse_point(raw_row.get('LocateTubewell/Tubeloc'))

            if points:
                ctr = [sum(p[0] for p in points)/len(points), sum(p[1] for p in points)/len(points)]
            elif tw_loc:
                ctr = tw_loc
            else:
                ctr = [30.7, 76.7]

            mini_m = folium.Map(location=ctr, zoom_start=16, tiles=None)
            folium.TileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", attr="CARTO", name="🗺️ Street").add_to(mini_m)
            folium.TileLayer("https://mt{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", attr="Google", name="🛰️ Satellite", subdomains=["0","1","2","3"], max_zoom=21).add_to(mini_m)
            folium.LayerControl(position="topright", collapsed=False).add_to(mini_m)

            poly_popup_html = f"""<div style="font-family:Arial,sans-serif;width:220px;font-size:12px;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.2)"><div style="background:#2d6a4f;color:white;padding:8px 12px"><b style="font-size:13px">🌾 {name_r}</b></div><div style="padding:10px 12px;background:#f9f9f9;border:1px solid #ddd;border-top:none"><table style="width:100%;border-collapse:collapse"><tr><td style="color:#666;padding:3px 0;width:45%">📍 Village</td><td><b>{village_r}</b></td></tr><tr><td style="color:#666;padding:3px 0">📞 Phone</td><td>{phone_r}</td></tr><tr><td style="color:#666;padding:3px 0">🎂 Age</td><td>{age_r}</td></tr><tr><td style="color:#666;padding:3px 0">🌾 Acres</td><td><b>{acres_r}</b></td></tr><tr><td style="color:#666;padding:3px 0">🏠 Ownership</td><td>{ownership_r}</td></tr><tr><td style="color:#666;padding:3px 0">💧 Method</td><td><b style="color:#2d6a4f">{method_r}</b></td></tr></table></div></div>"""

            tw_popup_html = f"""<div style="font-family:Arial,sans-serif;width:220px;font-size:12px;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.2)"><div style="background:#1d3557;color:white;padding:8px 12px"><b style="font-size:13px">🔧 Tubewell</b></div><div style="padding:10px 12px;background:#f0f6ff;border:1px solid #cce0ff;border-top:none"><table style="width:100%;border-collapse:collapse"><tr><td style="color:#666;padding:3px 0;width:50%">👤 Farmer</td><td><b>{name_r}</b></td></tr><tr><td style="color:#666;padding:3px 0">📞 Phone</td><td>{phone_r}</td></tr><tr><td style="color:#666;padding:3px 0">🌾 Acres</td><td>{acres_r}</td></tr><tr><td style="color:#666;padding:3px 0">📍 Village</td><td>{village_r}</td></tr><tr><td style="color:#666;padding:3px 0">⚙️ Horsepower</td><td>{hp_r}</td></tr><tr><td style="color:#666;padding:3px 0">📏 Delivery MM</td><td>{mm_r}</td></tr><tr><td style="color:#666;padding:3px 0">📐 Bore Depth</td><td><b>{bd_r} ft</b></td></tr><tr><td style="color:#666;padding:3px 0">💦 Water Level</td><td>{gwl_r} ft</td></tr></table></div></div>"""

            if points:
                folium.Polygon(
                    locations=points,
                    color='#2d6a4f', fill=True,
                    fill_color='#52b788', fill_opacity=0.5, weight=3,
                    popup=folium.Popup(poly_popup_html, max_width=240),
                    tooltip=f"🌾 {name_r} | {village_r} | {acres_r} ac | {method_r}"
                ).add_to(mini_m)
                mini_m.fit_bounds([
                    [min(p[0] for p in points), min(p[1] for p in points)],
                    [max(p[0] for p in points), max(p[1] for p in points)]
                ])
            else:
                st.caption("📍 No polygon data for this farm")

            if tw_loc:
                folium.Marker(
                    location=tw_loc,
                    popup=folium.Popup(tw_popup_html, max_width=240),
                    tooltip=f"🔧 {name_r}'s Tubewell — click for details",
                    icon=folium.Icon(color='blue', icon='tint', prefix='fa')
                ).add_to(mini_m)

            components.html(mini_m._repr_html_(), height=400)

        with st.expander("📋 View All Form Fields (70+ columns)"):
            skip = {'_attachments','_geolocation','_notes','_tags',
                    '_validation_status','formhub/uuid','meta/instanceID',
                    'meta/rootUuid','meta/deprecatedID','__version__',
                    '_xform_id_string','_uuid','_submitted_by','_status','_orig_pos'}
            all_data = {col: clean(raw_row.get(col,''))
                        for col in df_indexed.columns
                        if col not in skip and clean(raw_row.get(col,'')) != '—'}
            st.dataframe(
                pd.DataFrame(list(all_data.items()), columns=['Field','Value']),
                use_container_width=True, height=400
            )

st.markdown("---")

st.subheader("⬇️ Download Data")
dtab1, dtab2 = st.tabs(["📋 Key Columns (11)", "📦 Full Data (All Columns)"])
with dtab1:
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
            st.download_button("⬇️ Download Key Columns", data=export_key.to_csv(index=False).encode('utf-8'), file_name="farms_key.csv", mime="text/csv")
        elif fmt1 == "Excel":
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                export_key.to_excel(w, index=False, sheet_name='Farms')
            st.download_button("⬇️ Download Key Columns", data=buf.getvalue(), file_name="farms_key.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        elif fmt1 == "JSON":
            st.download_button("⬇️ Download Key Columns", data=export_key.to_json(orient='records', indent=2).encode('utf-8'), file_name="farms_key.json", mime="application/json")
with dtab2:
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
        drop_cols = [c for c in ['_orig_pos'] if c in export_full.columns]
        export_full = export_full.drop(columns=drop_cols)
        if 'Phone' in export_full.columns:
            export_full['Phone'] = export_full['Phone'].astype(str)
        if fmt2 == "CSV":
            st.download_button("⬇️ Download Full Data", data=export_full.to_csv(index=False).encode('utf-8'), file_name="farms_full.csv", mime="text/csv")
        elif fmt2 == "Excel":
            buf2 = io.BytesIO()
            with pd.ExcelWriter(buf2, engine='openpyxl') as w:
                export_full.to_excel(w, index=False, sheet_name='Full Data')
            st.download_button("⬇️ Download Full Data", data=buf2.getvalue(), file_name="farms_full.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        elif fmt2 == "JSON":
            st.download_button("⬇️ Download Full Data", data=export_full.to_json(orient='records', indent=2).encode('utf-8'), file_name="farms_full.json", mime="application/json")

st.caption("Data refreshes every 60 seconds from AWS database.")
