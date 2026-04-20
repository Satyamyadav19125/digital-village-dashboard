import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import plotly.express as px
import io
import folium
import math
import streamlit.components.v1 as components
from datetime import datetime

st.set_page_config(page_title="Digital Village Project", page_icon="🌾", layout="wide")

# ─── DATABASE CONNECTION ───────────────────────────────────────────────────────

@st.cache_resource
def get_engine():
    import os
    host = os.environ.get("DB_HOST") or st.secrets.get("DB_HOST")
    name = os.environ.get("DB_NAME") or st.secrets.get("DB_NAME")
    user = os.environ.get("DB_USER") or st.secrets.get("DB_USER")
    pwd  = os.environ.get("DB_PASS") or st.secrets.get("DB_PASS")
    return create_engine(f"postgresql://{user}:{pwd}@{host}:5432/{name}")

def ensure_edit_columns():
    """Auto-create edit columns in AWS if they don't exist yet."""
    engine = get_engine()
    edit_cols = [
        ("edited_village",      "TEXT"),
        ("edited_farmer_name",  "TEXT"),
        ("edited_acres",        "TEXT"),
        ("edited_method",       "TEXT"),
        ("verified",            "BOOLEAN DEFAULT FALSE"),
        ("notes",               "TEXT"),
        ("last_edited_by",      "TEXT"),
        ("last_edited_at",      "TIMESTAMP"),
    ]
    with engine.connect() as conn:
        for col_name, col_type in edit_cols:
            try:
                conn.execute(text(
                    f'ALTER TABLE farm_registrations ADD COLUMN IF NOT EXISTS "{col_name}" {col_type}'
                ))
            except Exception:
                pass
        conn.commit()

@st.cache_data(ttl=60)
def load_data():
    engine = get_engine()
    df = pd.read_sql('SELECT * FROM farm_registrations', engine)
    return df

def save_edits(row_id, edits: dict, editor_name: str):
    """Save edited values back to AWS for one farm row."""
    engine = get_engine()
    edits["last_edited_by"] = editor_name
    edits["last_edited_at"] = datetime.utcnow()
    set_clause = ", ".join([f'"{k}" = :{k}' for k in edits.keys()])
    query = text(f'UPDATE farm_registrations SET {set_clause} WHERE "_id" = :row_id')
    params = {**edits, "row_id": row_id}
    with engine.connect() as conn:
        conn.execute(query, params)
        conn.commit()

# ─── HELPER FUNCTIONS ─────────────────────────────────────────────────────────

def parse_polygon(poly_str):
    if not poly_str or str(poly_str) in ('None', 'nan'): return []
    pts = []
    for seg in str(poly_str).strip().split(';'):
        p = seg.strip().split()
        if len(p) >= 2:
            try: pts.append([float(p[0]), float(p[1])])
            except: pass
    return pts if len(pts) >= 3 else []

def parse_point(loc_str):
    if not loc_str or str(loc_str) in ('None', 'nan'): return None
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
    return '—' if s in ('nan', 'None', '') else s

def parse_pump(pump_str):
    if not pump_str or pump_str == '—': return '—', '—'
    try:
        raw   = str(pump_str).lower()
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

def build_mini_map(raw_row):
    name_r      = clean(raw_row.get('Demography/Namefarmer'))
    phone_r     = clean(raw_row.get('Demography/phnofarmer'))
    age_r       = clean(raw_row.get('Demography/agefarmer'))
    acres_r     = clean(raw_row.get('Facres/Acres'))
    village_r   = clean(raw_row.get('inthebeginning/Village'))
    ownership_r = clean(raw_row.get('Acerage/Own'))
    method_r    = clean(raw_row.get('Consent/TPR_DSR'))
    pump_r      = clean(raw_row.get('Tubewells/pump1'))
    bd_r        = clean(raw_row.get('Tubewells/BD1'))
    gwl_r       = clean(raw_row.get('GWL_001/GWL'))
    hp_r, mm_r  = parse_pump(pump_r)

    poly_str = raw_row.get('Poly1/map1') or raw_row.get('Poly2/map2') or raw_row.get('Poly3/map3')
    points   = parse_polygon(poly_str)
    tw_loc   = parse_point(raw_row.get('LocateTubewell/Tubeloc'))

    if points:
        ctr = [sum(p[0] for p in points)/len(points), sum(p[1] for p in points)/len(points)]
    elif tw_loc:
        ctr = tw_loc
    else:
        ctr = [30.7, 76.7]

    mini_m = folium.Map(location=ctr, zoom_start=16, tiles=None)
    folium.TileLayer(
        "https://mt{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google", name="🛰️ Satellite",
        subdomains=["0","1","2","3"], max_zoom=21
    ).add_to(mini_m)
    folium.TileLayer(
        "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        attr="CARTO", name="🗺️ Street"
    ).add_to(mini_m)
    folium.LayerControl(position="topright", collapsed=False).add_to(mini_m)

    poly_popup_html = (
        f"<div style='font-family:Arial,sans-serif;width:220px;font-size:12px;"
        f"border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.2)'>"
        f"<div style='background:#2d6a4f;color:white;padding:8px 12px'>"
        f"<b style='font-size:13px'>🌾 {name_r}</b></div>"
        f"<div style='padding:10px 12px;background:#f9f9f9;border:1px solid #ddd;border-top:none'>"
        f"<table style='width:100%;border-collapse:collapse'>"
        f"<tr><td style='color:#666;padding:3px 0;width:45%'>📍 Village</td><td><b>{village_r}</b></td></tr>"
        f"<tr><td style='color:#666;padding:3px 0'>📞 Phone</td><td>{phone_r}</td></tr>"
        f"<tr><td style='color:#666;padding:3px 0'>🎂 Age</td><td>{age_r}</td></tr>"
        f"<tr><td style='color:#666;padding:3px 0'>🌾 Acres</td><td><b>{acres_r}</b></td></tr>"
        f"<tr><td style='color:#666;padding:3px 0'>🏠 Ownership</td><td>{ownership_r}</td></tr>"
        f"<tr><td style='color:#666;padding:3px 0'>💧 Method</td>"
        f"<td><b style='color:#2d6a4f'>{method_r}</b></td></tr>"
        f"</table></div></div>"
    )
    tw_popup_html = (
        f"<div style='font-family:Arial,sans-serif;width:220px;font-size:12px;"
        f"border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.2)'>"
        f"<div style='background:#1d3557;color:white;padding:8px 12px'>"
        f"<b style='font-size:13px'>🔧 Tubewell</b></div>"
        f"<div style='padding:10px 12px;background:#f0f6ff;border:1px solid #cce0ff;border-top:none'>"
        f"<table style='width:100%;border-collapse:collapse'>"
        f"<tr><td style='color:#666;padding:3px 0;width:50%'>👤 Farmer</td><td><b>{name_r}</b></td></tr>"
        f"<tr><td style='color:#666;padding:3px 0'>📞 Phone</td><td>{phone_r}</td></tr>"
        f"<tr><td style='color:#666;padding:3px 0'>📍 Village</td><td>{village_r}</td></tr>"
        f"<tr><td style='color:#666;padding:3px 0'>⚙️ Horsepower</td><td>{hp_r}</td></tr>"
        f"<tr><td style='color:#666;padding:3px 0'>📏 Delivery MM</td><td>{mm_r}</td></tr>"
        f"<tr><td style='color:#666;padding:3px 0'>📐 Bore Depth</td><td>{bd_r} ft</td></tr>"
        f"<tr><td style='color:#666;padding:3px 0'>💦 Water Level</td><td>{gwl_r} ft</td></tr>"
        f"</table></div></div>"
    )

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

# ─── SETUP ────────────────────────────────────────────────────────────────────

ensure_edit_columns()

df         = load_data()
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

# ─── HEADER ───────────────────────────────────────────────────────────────────

st.title("🌾 Digital Village Project")
st.markdown("**Tel Aviv University | Thapar University, Patiala**")
st.markdown("---")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Farms", len(df_indexed))
col2.metric("Villages", df_display['Village'].nunique() if 'Village' in df_display else "—")
col3.metric("Blocks", df_display['Village'].nunique() if 'Village' in df_display else "—")
col4.metric("Latest Submission", str(df_display['Submitted At'].max())[:10] if 'Submitted At' in df_display else "—")
st.markdown("---")

# ─── OVERVIEW CHARTS ──────────────────────────────────────────────────────────

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
        fig2.update_layout(
            height=400,
            legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.0),
            margin=dict(r=120)
        )
        st.plotly_chart(fig2, use_container_width=True)
st.markdown("---")

# ─── FILTERS ──────────────────────────────────────────────────────────────────

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
st.markdown("---")

# ─── TWO MAIN TABS ────────────────────────────────────────────────────────────

tab_raw, tab_edit = st.tabs(["📋 Raw Data  (Kobo — Read Only)", "✏️ Edited Data  (Your Manual Edits)"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — RAW DATA
# ══════════════════════════════════════════════════════════════════════════════

with tab_raw:
    st.subheader("📋 Farm Registrations — Raw Kobo Data")
    st.info("🔒 This tab shows the original data exactly as submitted through KoboToolbox. Nothing here can be changed.", icon="ℹ️")

    display_cols = [c for c in ['Farmer Name', 'Village', 'Phone', 'Age',
                    'Acres', 'Ownership', 'Method', 'Enumerator',
                    'Date', 'Submitted At'] if c in filtered.columns]

    selected_raw = st.dataframe(
        filtered[display_cols],
        use_container_width=True,
        height=400,
        on_select="rerun",
        selection_mode="single-row",
    )

    selected_rows_raw = selected_raw.selection.rows if selected_raw.selection else []
    if selected_rows_raw:
        st.session_state['raw_farmer_idx'] = selected_rows_raw[0]
    elif 'raw_farmer_idx' in st.session_state:
        del st.session_state['raw_farmer_idx']

    if 'raw_farmer_idx' in st.session_state:
        row_idx = st.session_state['raw_farmer_idx']
        if row_idx < len(filtered):
            farmer_display = filtered.iloc[row_idx]
            farmer_name    = clean(farmer_display.get('Farmer Name', 'Unknown'))
            orig_pos       = int(farmer_display['_orig_pos'])
            raw_row        = df_indexed.iloc[orig_pos]

            st.markdown("---")
            st.subheader(f"🌾 Farm Profile — {farmer_name}")

            i1, i2, i3, i4 = st.columns(4)
            i1.metric("Village",   clean(farmer_display.get('Village','—')))
            i2.metric("Acres",     clean(farmer_display.get('Acres','—')))
            i3.metric("Method",    clean(farmer_display.get('Method','—')))
            i4.metric("Ownership", clean(farmer_display.get('Ownership','—')))

            left, right = st.columns([1, 1.5])
            with left:
                st.markdown("##### 👤 Farmer Details")
                for k, v in {
                    "📞 Phone":      clean(farmer_display.get('Phone','—')),
                    "🎂 Age":        clean(farmer_display.get('Age','—')),
                    "🎓 Education":  clean(farmer_display.get('Education','—')),
                    "👷 Enumerator": clean(farmer_display.get('Enumerator','—')),
                    "📅 Date":       clean(farmer_display.get('Date','—')),
                    "🕐 Submitted":  clean(farmer_display.get('Submitted At','—')),
                }.items():
                    if v != '—':
                        st.markdown(f"**{k}:** {v}")

                st.markdown("##### 🔧 Tubewell Details")
                hp1, mm1 = parse_pump(clean(raw_row.get('Tubewells/pump1','—')))
                hp2, mm2 = parse_pump(clean(raw_row.get('Tubewells/pump2','—')))
                for k, v in {
                    "🔧 No. Tubewells": clean(raw_row.get('Tubewells/Tubewells_001','—')),
                    "⚙️ Horsepower 1":  hp1,
                    "📏 Delivery MM 1": mm1,
                    "📐 Bore Depth 1":  clean(raw_row.get('Tubewells/BD1','—')) + " ft",
                    "⚙️ Horsepower 2":  hp2,
                    "📏 Delivery MM 2": mm2,
                    "📐 Bore Depth 2":  clean(raw_row.get('Tubewells/BD2','—')) + " ft",
                    "💦 Water Level":   clean(raw_row.get('GWL_001/GWL','—')) + " ft",
                    "🤝 Tube Share":    clean(raw_row.get('GWL_001/Tubeshare','—')),
                }.items():
                    if '—' not in v:
                        st.markdown(f"**{k}:** {v}")

            with right:
                st.markdown("##### 🗺️ Farm Location")
                build_mini_map(raw_row)

            with st.expander("📋 View All Form Fields (70+ columns)"):
                skip = {
                    '_attachments','_geolocation','_notes','_tags',
                    '_validation_status','formhub/uuid','meta/instanceID',
                    'meta/rootUuid','meta/deprecatedID','__version__',
                    '_xform_id_string','_uuid','_submitted_by','_status','_orig_pos',
                    'edited_village','edited_farmer_name','edited_acres','edited_method',
                    'verified','notes','last_edited_by','last_edited_at'
                }
                all_data = {
                    col: clean(raw_row.get(col,''))
                    for col in df_indexed.columns
                    if col not in skip and clean(raw_row.get(col,'')) != '—'
                }
                st.dataframe(
                    pd.DataFrame(list(all_data.items()), columns=['Field','Value']),
                    use_container_width=True,
                    height=400
                )

    st.markdown("---")
    st.subheader("⬇️ Download Raw Data")
    dtab1, dtab2 = st.tabs(["📋 Key Columns", "📦 Full Raw Data"])
    with dtab1:
        d1, d2 = st.columns([1,1])
        with d1:
            fmt1 = st.selectbox("Format:", ["CSV","Excel","JSON"], key="raw_fmt1")
        with d2:
            st.write("")
            export_key = filtered[display_cols].copy().reset_index()
            if 'Phone' in export_key.columns:
                export_key['Phone'] = export_key['Phone'].astype(str)
            if fmt1 == "CSV":
                st.download_button("⬇️ Download", data=export_key.to_csv(index=False).encode('utf-8'), file_name="raw_farms_key.csv", mime="text/csv")
            elif fmt1 == "Excel":
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as w:
                    export_key.to_excel(w, index=False, sheet_name='Raw Key')
                st.download_button("⬇️ Download", data=buf.getvalue(), file_name="raw_farms_key.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            elif fmt1 == "JSON":
                st.download_button("⬇️ Download", data=export_key.to_json(orient='records', indent=2).encode('utf-8'), file_name="raw_farms_key.json", mime="application/json")
    with dtab2:
        d3, d4 = st.columns([1,1])
        with d3:
            fmt2 = st.selectbox("Format:", ["CSV","Excel","JSON"], key="raw_fmt2")
        with d4:
            st.write("")
            export_full = filtered.copy().reset_index(drop=True)
            export_full.index = export_full.index + 1
            export_full.index.name = 'No.'
            export_full = export_full.reset_index()
            edit_col_names = ['_orig_pos','edited_village','edited_farmer_name','edited_acres',
                              'edited_method','verified','notes','last_edited_by','last_edited_at']
            drop_cols = [c for c in edit_col_names if c in export_full.columns]
            export_full = export_full.drop(columns=drop_cols)
            if 'Phone' in export_full.columns:
                export_full['Phone'] = export_full['Phone'].astype(str)
            if fmt2 == "CSV":
                st.download_button("⬇️ Download", data=export_full.to_csv(index=False).encode('utf-8'), file_name="raw_farms_full.csv", mime="text/csv")
            elif fmt2 == "Excel":
                buf2 = io.BytesIO()
                with pd.ExcelWriter(buf2, engine='openpyxl') as w:
                    export_full.to_excel(w, index=False, sheet_name='Raw Full')
                st.download_button("⬇️ Download", data=buf2.getvalue(), file_name="raw_farms_full.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            elif fmt2 == "JSON":
                st.download_button("⬇️ Download", data=export_full.to_json(orient='records', indent=2).encode('utf-8'), file_name="raw_farms_full.json", mime="application/json")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — EDITED DATA
# ══════════════════════════════════════════════════════════════════════════════

with tab_edit:
    st.subheader("✏️ Farm Registrations — With Your Manual Edits")
    st.success("✅ This tab shows Kobo data + your corrections. Click any row to edit it. Changes are saved to AWS instantly.", icon="✏️")

    editor_name = st.text_input("👤 Your name (saved with each edit)", placeholder="e.g. Satyam", key="editor_name")

    edit_filtered = filtered.copy()

    if 'verified' in edit_filtered.columns:
        edit_filtered['Verified'] = edit_filtered['verified'].apply(
            lambda x: "✅ Yes" if str(x).lower() in ('true','1','t','yes') else "—"
        )
    else:
        edit_filtered['Verified'] = "—"

    if 'edited_village' in edit_filtered.columns:
        edit_filtered['Edited Village'] = edit_filtered['edited_village'].apply(
            lambda x: f"📝 {x}" if x and str(x) not in ('nan','None','') else "—"
        )
    else:
        edit_filtered['Edited Village'] = "—"

    if 'notes' in edit_filtered.columns:
        edit_filtered['Notes'] = edit_filtered['notes'].apply(
            lambda x: str(x)[:30]+"…" if x and str(x) not in ('nan','None','') and len(str(x))>30
            else (str(x) if x and str(x) not in ('nan','None','') else "—")
        )
    else:
        edit_filtered['Notes'] = "—"

    if 'last_edited_by' in edit_filtered.columns:
        edit_filtered['Last Edited By'] = edit_filtered['last_edited_by'].apply(
            lambda x: str(x) if x and str(x) not in ('nan','None','') else "—"
        )
    else:
        edit_filtered['Last Edited By'] = "—"

    edit_display_cols = [c for c in ['Farmer Name', 'Village', 'Phone', 'Acres', 'Method', 'Submitted At'] if c in edit_filtered.columns]
    table_cols = edit_display_cols + ['Edited Village', 'Verified', 'Notes', 'Last Edited By']
    table_cols = [c for c in table_cols if c in edit_filtered.columns]

    selected_edit = st.dataframe(
        edit_filtered[table_cols],
        use_container_width=True,
        height=400,
        on_select="rerun",
        selection_mode="single-row",
    )

    selected_rows_edit = selected_edit.selection.rows if selected_edit.selection else []
    if selected_rows_edit:
        st.session_state['edit_farmer_idx'] = selected_rows_edit[0]
    elif 'edit_farmer_idx' in st.session_state:
        del st.session_state['edit_farmer_idx']

    if 'edit_farmer_idx' in st.session_state:
        row_idx = st.session_state['edit_farmer_idx']
        if row_idx < len(edit_filtered):
            farmer_display = edit_filtered.iloc[row_idx]
            farmer_name    = clean(farmer_display.get('Farmer Name', 'Unknown'))
            orig_pos       = int(farmer_display['_orig_pos'])
            raw_row        = df_indexed.iloc[orig_pos]
            row_id         = raw_row.get('_id')

            st.markdown("---")
            st.subheader(f"✏️ Edit Farm — {farmer_name}")
            st.caption("Left column = raw Kobo value (cannot change). Right column = your correction.")

            cur_village  = clean(raw_row.get('edited_village',''))
            cur_name     = clean(raw_row.get('edited_farmer_name',''))
            cur_acres    = clean(raw_row.get('edited_acres',''))
            cur_method   = clean(raw_row.get('edited_method',''))
            cur_verified = str(raw_row.get('verified','')).lower() in ('true','1','t','yes')
            cur_notes    = clean(raw_row.get('notes',''))

            st.markdown("#### 📝 Correct the Fields")
            ea, eb = st.columns(2)
            with ea:
                st.markdown("**Raw Kobo Value (read only)**")
                st.text_input("Village (raw)",      value=clean(raw_row.get('inthebeginning/Village','')), disabled=True, key="rv_village")
                st.text_input("Farmer Name (raw)",  value=clean(raw_row.get('Demography/Namefarmer','')),  disabled=True, key="rv_name")
                st.text_input("Acres (raw)",         value=clean(raw_row.get('Facres/Acres','')),           disabled=True, key="rv_acres")
                st.text_input("Method (raw)",        value=clean(raw_row.get('Consent/TPR_DSR','')),        disabled=True, key="rv_method")
            with eb:
                st.markdown("**Your Corrected Value**")
                new_village = st.text_input("Village (edited)",      value="" if cur_village=='—' else cur_village, key="ev_village")
                new_name    = st.text_input("Farmer Name (edited)",  value="" if cur_name=='—' else cur_name,       key="ev_name")
                new_acres   = st.text_input("Acres (edited)",        value="" if cur_acres=='—' else cur_acres,     key="ev_acres")
                new_method  = st.selectbox("Method (edited)",
                                options=["", "TPR", "DSR"],
                                index=0 if cur_method=='—' else (["","TPR","DSR"].index(cur_method) if cur_method in ["","TPR","DSR"] else 0),
                                key="ev_method")

            st.markdown("#### 🗒️ Extra Fields")
            new_verified = st.checkbox("✅ Mark this farm as Verified", value=cur_verified, key="ev_verified")
            new_notes    = st.text_area("📝 Notes / Comments", value="" if cur_notes=='—' else cur_notes, height=100, key="ev_notes")

            st.markdown("")
            save_col, _ = st.columns([1, 4])
            with save_col:
                save_clicked = st.button("💾 Save Changes to AWS", type="primary", key="save_btn")

            if save_clicked:
                if not editor_name.strip():
                    st.warning("⚠️ Please enter your name at the top of this tab before saving.")
                elif row_id is None:
                    st.error("❌ Cannot save — this row has no _id in the database.")
                else:
                    edits = {
                        "edited_village":     new_village or None,
                        "edited_farmer_name": new_name    or None,
                        "edited_acres":       new_acres   or None,
                        "edited_method":      new_method  or None,
                        "verified":           new_verified,
                        "notes":              new_notes   or None,
                    }
                    try:
                        save_edits(row_id, edits, editor_name.strip())
                        st.success(f"✅ Changes saved to AWS for **{farmer_name}**! Dashboard will refresh in 60 seconds.")
                        st.cache_data.clear()
                    except Exception as e:
                        st.error(f"❌ Save failed: {e}")

    st.markdown("---")
    st.subheader("⬇️ Download Edited Data")
    st.caption("Downloads Kobo columns + all your manual edit columns combined.")

    de1, de2 = st.columns([1,1])
    with de1:
        fmt_edit = st.selectbox("Format:", ["CSV","Excel","JSON"], key="edit_fmt")
    with de2:
        st.write("")
        export_edit = edit_filtered.copy().reset_index(drop=True)
        export_edit.index = export_edit.index + 1
        export_edit.index.name = 'No.'
        export_edit = export_edit.reset_index()

        keep_edit_cols = ['No.'] + [c for c in display_cols if c in export_edit.columns] + \
                         ['edited_village','edited_farmer_name','edited_acres','edited_method',
                          'verified','notes','last_edited_by','last_edited_at']
        keep_edit_cols = [c for c in keep_edit_cols if c in export_edit.columns]
        export_edit = export_edit[keep_edit_cols]

        if 'Phone' in export_edit.columns:
            export_edit['Phone'] = export_edit['Phone'].astype(str)

        if fmt_edit == "CSV":
            st.download_button("⬇️ Download Edited Data", data=export_edit.to_csv(index=False).encode('utf-8'), file_name="edited_farms.csv", mime="text/csv")
        elif fmt_edit == "Excel":
            buf_e = io.BytesIO()
            with pd.ExcelWriter(buf_e, engine='openpyxl') as w:
                export_edit.to_excel(w, index=False, sheet_name='Edited Data')
            st.download_button("⬇️ Download Edited Data", data=buf_e.getvalue(), file_name="edited_farms.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        elif fmt_edit == "JSON":
            st.download_button("⬇️ Download Edited Data", data=export_edit.to_json(orient='records', indent=2).encode('utf-8'), file_name="edited_farms.json", mime="application/json")

st.markdown("---")
st.caption("Data refreshes every 60 seconds from AWS database.")
