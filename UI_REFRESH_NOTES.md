# CivicFlow UI refresh notes

This version replaces the rigid, horizontal-tab prototype with a civic-operations workspace and a task-oriented navigation rail.

## Main changes

- Editorial dashboard design: warm grey background, deep-green navigation, quiet borders, restrained severity/status chips, and clear page hierarchy.
- Interactive Leaflet maps on Overview, Incidents, New report, Dispatch and Insights. Markers cluster by sector and open case popups.
- Searchable and filterable work-order register with editable status/department/team/affected estimate and CSV export.
- New report path split into intake, location context and triage review, with a deliberate confirmation step before creating the work order.
- Dispatch assignment form, crew workload counts, team-filtered map, sector run sheet and downloadable dispatch CSV.
- Human-reviewed before/after closure flow and an Insights page for department/severity distribution.
- Visuals and labels distinguish model-assisted analysis from offline keyword-demo rules.

## Map accuracy notice

The map uses approximate sector-centroid points for illustration. It does not represent exact citizen GPS coordinates, live municipal feeds, road-following routes, traffic-aware optimization, or ETAs.

## Update an existing Codespace

Back up any local modifications first. Replace `app.py`, `requirements.txt`, `README.md`, `DEMO_SCRIPT.md`, and `.streamlit/config.toml` with the matching files from this project. Then run:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The explicit `python -m streamlit` form also works when the `streamlit` executable is not on PATH.
