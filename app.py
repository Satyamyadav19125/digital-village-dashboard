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
