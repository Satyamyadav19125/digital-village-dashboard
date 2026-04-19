import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import plotly.express as px
import io
import folium
import json
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

def build_farm_map(row):
    poly_str = row.get('Poly1/map1') or row.get('Poly2/map2') or row.get('Poly3/map3')
    points   = parse_polygon(poly_str)
    tw_loc   = parse_point(row.get('LocateTubewell/Tubeloc'))

    # Map center
    if points:
        ctr = [sum(p[0] for p in points)/len(points),
               sum(p[1] for p in points)/len(points)]
    elif tw_loc:
        ctr = tw_loc
    else:
        ctr = [30.7, 76.7]

    m = folium.Map(location=ctr, zoom_start=16, tiles=None)
    folium.TileLayer(
        "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        attr="CARTO", name="🗺️ Street"
    ).add_to(m)
    folium.TileLayer(
        "https://mt{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google", name="🛰️ Satellite",
        subdomains=["0","1","2","3"], max_zoom=21
    ).add_to(m)
    folium.LayerControl(position="topright", collapsed=False).add_to(m)

    name = clean(row.get('Demography/Namefarmer'))

    if points:
        calc_ac = calc_area(points)
        folium.Polygon(
            locations=points,
            color='#2d6a4f', fill=True,
            fill_color='#52b788', fill_opacity=0.5, weight=2,
            tooltip=f"🌾 {name}'s Farm" + (f" | ~{calc_ac} ac" if calc_ac else "")
        ).add_to(m)
        m.fit_bounds([[min(p[0] for p in points), min(p[1] for p in points)],
                      [max(p[0] for p in points), max(p[1] for p in points)]])

    if tw_loc:
        folium.Marker(
            location=tw_loc,
            tooltip=f"🔧 {name}'s Tubewell",
            icon=folium.Icon(color='blue', icon='tint', prefix='fa')
        ).add_to(m)

    return m._repr_html_()

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

# ── Tabs ──────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 Overview", "📋 Farm Registrations", "🗺️ Farm Map"])

# ── TAB 1: Charts ─────────────────────────────────────
with tab1:
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

# ── TAB 2: Farm Registrations ─────────────────────────
with tab2:
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
    filtered = filtered.reset_index(drop=True)
    filtered.index = filtered.index + 1
    filtered.index.name = 'No.'

    st.caption(f"Showing {len(filtered)} of {len(df_display)} records")
    st.subheader("📋 Farm Registrations")

    display_cols = [c for c in ['Farmer Name', 'Village', 'Phone', 'Age',
                    'Acres', 'Ownership', 'Method', 'Enumerator',
                    'Date', 'Submitted At'] if c in filtered.columns]

    # ── Selectable table ──────────────────────────────
    selected = st.dataframe(
        filtered[display_cols],
        use_container_width=True,
        height=400,
        on_select="rerun",
        selection_mode="single-row",
    )

    # ── View Farm Profile button ──────────────────────
    selected_rows = selected.selection.rows if selected.selection else []
    if selected_rows:
        row_idx = selected_rows[0]
        farmer_display = filtered.iloc[row_idx]
        farmer_name = farmer_display.get('Farmer Name', 'Unknown')

        st.markdown("---")
        if st.button(f"👁️ View Farm Profile — {farmer_name}", type="primary", use_container_width=True):
            st.session_state['view_farmer_idx'] = row_idx
            st.session_state['view_farmer_filtered'] = filtered.index[row_idx]

    # ── Farm Profile ──────────────────────────────────
    if 'view_farmer_idx' in st.session_state:
        row_idx = st.session_state['view_farmer_idx']
        if row_idx < len(filtered):
            farmer_display = filtered.iloc[row_idx]
            farmer_name = clean(farmer_display.get('Farmer Name', 'Unknown'))

            # Get original raw row for map + full details
            orig_idx = filtered.index[row_idx] - 1
            raw_row  = df.iloc[orig_idx] if orig_idx < len(df) else None

            st.markdown("---")
            st.subheader(f"🌾 Farm Profile — {farmer_name}")

            # ── Info cards ────────────────────────────
            i1, i2, i3, i4 = st.columns(4)
            i1.metric("Village",   clean(farmer_display.get('Village', '—')))
            i2.metric("Acres",     clean(farmer_display.get('Acres', '—')))
            i3.metric("Method",    clean(farmer_display.get('Method', '—')))
            i4.metric("Ownership", clean(farmer_display.get('Ownership', '—')))

            # ── Two columns: details + map ────────────
            left, right = st.columns([1, 1.5])

            with left:
                st.markdown("##### 👤 Farmer Details")
                details = {
                    "📞 Phone":      clean(farmer_display.get('Phone', '—')),
                    "🎂 Age":        clean(farmer_display.get('Age', '—')),
                    "🎓 Education":  clean(farmer_display.get('Education', '—')),
                    "👷 Enumerator": clean(farmer_display.get('Enumerator', '—')),
                    "📅 Date":       clean(farmer_display.get('Date', '—')),
                    "🕐 Submitted":  clean(farmer_display.get('Submitted At', '—')),
                }
                for k, v in details.items():
                    st.markdown(f"**{k}:** {v}")

                if raw_row is not None:
                    st.markdown("##### 🔧 Tubewell Details")
                    tw_details = {
                        "🔧 No. of Tubewells": clean(raw_row.get('Tubewells/Tubewells_001', '—')),
                        "⚙️ Pump 1":           clean(raw_row.get('Tubewells/pump1', '—')),
                        "📏 Bore Depth 1":     clean(raw_row.get('Tubewells/BD1', '—')) + " ft",
                        "⚙️ Pump 2":           clean(raw_row.get('Tubewells/pump2', '—')),
                        "📏 Bore Depth 2":     clean(raw_row.get('Tubewells/BD2', '—')) + " ft",
                        "💦 GWL":              clean(raw_row.get('GWL_001/GWL', '—')) + " ft",
                        "🤝 Tube Share":       clean(raw_row.get('GWL_001/Tubeshare', '—')),
                    }
                    for k, v in tw_details.items():
                        if '—' not in v:
                            st.markdown(f"**{k}:** {v}")

            with right:
                st.markdown("##### 🗺️ Farm Location")
                if raw_row is not None:
                    map_html = build_farm_map(raw_row)
                    components.html(map_html, height=380)
                else:
                    st.info("Map not available")

            # ── Full form expander ────────────────────
            if raw_row is not None:
                with st.expander("📋 View All Form Fields (70+ columns)"):
                    skip = {'_attachments','_geolocation','_notes','_tags',
                            '_validation_status','formhub/uuid','meta/instanceID',
                            'meta/rootUuid','meta/deprecatedID','__version__',
                            '_xform_id_string','_uuid','_submitted_by','_status'}
                    all_data = {}
                    for col in df.columns:
                        if col in skip: continue
                        val = clean(raw_row.get(col, ''))
                        if val != '—':
                            all_data[col] = val
                    all_df = pd.DataFrame(list(all_data.items()), columns=['Field', 'Value'])
                    st.dataframe(all_df, use_container_width=True, height=400)

            if st.button("✖️ Close Profile"):
                del st.session_state['view_farmer_idx']
                st.rerun()

    st.markdown("---")

    # ── Download ──────────────────────────────────────
    st.subheader("⬇️ Download Data")
    dtab1, dtab2 = st.tabs(["📋 Key Columns", "📦 Full Data"])
    with dtab1:
        d1, d2 = st.columns([1, 1])
        with d1:
            fmt1 = st.selectbox("Format:", ["CSV", "Excel", "JSON"], key="fmt1")
        with d2:
            st.write("")
            export_key = filtered[display_cols].copy().reset_index()
            if 'Phone' in export_key.columns:
                export_key['Phone'] = export_key['Phone'].astype(str)
            if fmt1 == "CSV":
                st.download_button("⬇️ Download", data=export_key.to_csv(index=False).encode('utf-8'), file_name="farms_key.csv", mime="text/csv")
            elif fmt1 == "Excel":
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as w:
                    export_key.to_excel(w, index=False, sheet_name='Farms')
                st.download_button("⬇️ Download", data=buf.getvalue(), file_name="farms_key.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            elif fmt1 == "JSON":
                st.download_button("⬇️ Download", data=export_key.to_json(orient='records', indent=2).encode('utf-8'), file_name="farms_key.json", mime="application/json")
    with dtab2:
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
                st.download_button("⬇️ Download", data=export_full.to_csv(index=False).encode('utf-8'), file_name="farms_full.csv", mime="text/csv")
            elif fmt2 == "Excel":
                buf2 = io.BytesIO()
                with pd.ExcelWriter(buf2, engine='openpyxl') as w:
                    export_full.to_excel(w, index=False, sheet_name='Full Data')
                st.download_button("⬇️ Download", data=buf2.getvalue(), file_name="farms_full.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            elif fmt2 == "JSON":
                st.download_button("⬇️ Download", data=export_full.to_json(orient='records', indent=2).encode('utf-8'), file_name="farms_full.json", mime="application/json")

# ── TAB 3: Farm Map ───────────────────────────────────
with tab3:
    st.subheader("🗺️ Farm Map — Polygon View")
    st.caption("Green polygons = farm boundaries. Blue markers = tubewells. Click any farm or tubewell to see details.")

    def parse_polygon_map(poly_str):
        if not poly_str or str(poly_str) == 'None' or str(poly_str) == 'nan':
            return None
        try:
            points = []
            for point in str(poly_str).strip().split(';'):
                parts = point.strip().split()
                if len(parts) >= 2:
                    lat, lng = float(parts[0]), float(parts[1])
                    points.append([lat, lng])
            return points if len(points) >= 3 else None
        except:
            return None

    def parse_point_map(loc_str):
        if not loc_str or str(loc_str) == 'None' or str(loc_str) == 'nan':
            return None
        try:
            parts = str(loc_str).strip().split()
            if len(parts) >= 2:
                return float(parts[0]), float(parts[1])
        except:
            return None

    def clean_map(val, fallback="—"):
        if val is None or str(val) == 'nan' or str(val) == 'None':
            return fallback
        return str(val)

    m = folium.Map(location=[30.7, 76.7], zoom_start=11)
    folium.TileLayer(tiles='OpenStreetMap', name='🗺️ Street Map', control=True).add_to(m)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri', name='🛰️ Satellite', control=True
    ).add_to(m)

    farms_drawn = 0
    tubewells_drawn = 0

    for _, row in df.iterrows():
        name      = clean_map(row.get('Demography/Namefarmer'))
        village   = clean_map(row.get('inthebeginning/Village'))
        phone     = clean_map(row.get('Demography/phnofarmer'))
        age       = clean_map(row.get('Demography/agefarmer'))
        acres     = clean_map(row.get('Facres/Acres'))
        ownership = clean_map(row.get('Acerage/Own'))
        method    = clean_map(row.get('Consent/TPR_DSR'))
        tubewells = clean_map(row.get('Tubewells/Tubewells_001'))
        pump      = clean_map(row.get('Tubewells/pump1'))
        bd        = clean_map(row.get('Tubewells/BD1'))
        gwl       = clean_map(row.get('GWL_001/GWL'))
        tubeshare = clean_map(row.get('GWL_001/Tubeshare'))

        popup_html = f"""
        <div style="font-family:Arial,sans-serif;width:240px;font-size:13px;">
            <div style="background:#2d6a4f;color:white;padding:8px 12px;border-radius:6px 6px 0 0;">
                <b style="font-size:15px;">🌾 {name}</b>
            </div>
            <div style="padding:10px 12px;background:#f9f9f9;border:1px solid #ddd;border-top:none;border-radius:0 0 6px 6px;">
                <table style="width:100%;border-collapse:collapse;">
                    <tr><td style="color:#666;padding:3px 0;">📍 Village</td><td style="font-weight:bold;">{village}</td></tr>
                    <tr><td style="color:#666;padding:3px 0;">📞 Phone</td><td>{phone}</td></tr>
                    <tr><td style="color:#666;padding:3px 0;">🎂 Age</td><td>{age}</td></tr>
                    <tr><td colspan="2"><hr style="margin:5px 0;border-color:#eee;"></td></tr>
                    <tr><td style="color:#666;padding:3px 0;">🌾 Acres</td><td style="font-weight:bold;">{acres}</td></tr>
                    <tr><td style="color:#666;padding:3px 0;">🏠 Ownership</td><td>{ownership}</td></tr>
                    <tr><td style="color:#666;padding:3px 0;">💧 Method</td><td><b style="color:#2d6a4f;">{method}</b></td></tr>
                    <tr><td colspan="2"><hr style="margin:5px 0;border-color:#eee;"></td></tr>
                    <tr><td style="color:#666;padding:3px 0;">🔧 Tubewells</td><td>{tubewells}</td></tr>
                    <tr><td style="color:#666;padding:3px 0;">⚙️ Pump</td><td>{pump}</td></tr>
                    <tr><td style="color:#666;padding:3px 0;">📏 Bore Depth</td><td>{bd} ft</td></tr>
                    <tr><td style="color:#666;padding:3px 0;">💦 GWL</td><td>{gwl} ft</td></tr>
                    <tr><td style="color:#666;padding:3px 0;">🤝 Tube Share</td><td>{tubeshare}</td></tr>
                </table>
            </div>
        </div>"""

        poly_str = row.get('Poly1/map1') or row.get('Poly2/map2') or row.get('Poly3/map3')
        points = parse_polygon_map(poly_str)
        if points:
            folium.Polygon(
                locations=points, color='#2d6a4f', fill=True,
                fill_color='#52b788', fill_opacity=0.4, weight=2,
                popup=folium.Popup(popup_html, max_width=270)
            ).add_to(m)
            farms_drawn += 1

        tube_loc = parse_point_map(row.get('LocateTubewell/Tubeloc'))
        if tube_loc:
            tube_popup = f"""
            <div style="font-family:Arial;width:200px;font-size:13px;">
                <div style="background:#1d3557;color:white;padding:6px 10px;border-radius:6px 6px 0 0;">
                    <b>🔧 Tubewell</b> — {name}
                </div>
                <div style="padding:8px 10px;background:#f9f9f9;border:1px solid #ddd;border-top:none;border-radius:0 0 6px 6px;">
                    <b>Village:</b> {village}<br>
                    <b>Tubewells:</b> {tubewells}<br>
                    <b>Pump:</b> {pump}<br>
                    <b>Bore Depth:</b> {bd} ft<br>
                    <b>GWL:</b> {gwl} ft<br>
                    <b>Sharing:</b> {tubeshare}
                </div>
            </div>"""
            folium.Marker(
                location=tube_loc,
                popup=folium.Popup(tube_popup, max_width=220),
                tooltip=f"🔧 {name}'s Tubewell",
                icon=folium.Icon(color='blue', icon='tint', prefix='fa')
            ).add_to(m)
            tubewells_drawn += 1

    folium.LayerControl(position='topright').add_to(m)
    st.caption(f"🌾 {farms_drawn} farm polygons | 🔧 {tubewells_drawn} tubewells")
    components.html(m._repr_html_(), height=600)

st.caption("Data refreshes every 60 seconds from AWS database.")
