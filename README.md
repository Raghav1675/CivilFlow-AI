# CivicFlow — Chandigarh Civic Operations Prototype

**Challenge track:** Civic Services  
**Pitch:** Turn fragmented citizen reports into prioritized, assigned, and human-reviewed civic work orders.

CivicFlow is a Streamlit prototype for a municipal operations desk. It is designed around a practical staff workflow rather than a generic chatbot: intake a report, triage it, check for related cases, assign a team, organise work by sector, review completion evidence, and export the work register.

## What's improved in this version

- **Operations overview:** priority-ranked queue, open/unassigned/critical counts, departmental workload chart, and interactive incident map.
- **Leaflet map:** Folium + Leaflet with clustered markers, severity colors, popups, layer control, and full-screen mode.
- **Searchable work register:** filters for status, severity and department; work-order details; edit status, owner, department and affected estimate; CSV export.
- **Guided intake:** citizen description and optional image, sector context map, analysis preview, duplicate candidates and an explicit confirmation step before the case enters the queue.
- **Field dispatch board:** team assignment, status update, map filter by crew, sector-grouped run sheet and CSV download.
- **Closure review:** before/after evidence, optional Gemini/Gemma model assistance, mandatory human confirmation before marking a work order resolved.
- **Insights:** departmental workload, severity breakdown, issue-type counts and map view.
- **Demo mode:** transparent keyword rules let judges walk through the workflow without API credentials. The interface labels this as demo logic, not AI inference.
- **Google AI API modes:** use a Gemini model or a Gemma endpoint enabled for your account for multimodal issue triage and evidence comparison.
- **Apache-2.0 license** for the project source.

## Run in GitHub Codespaces or locally

Python 3.10+ is recommended.

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Use `python -m streamlit` rather than relying on the standalone `streamlit` command if the executable is not on your PATH. Streamlit prints the local URL and, in Codespaces, usually offers to open the forwarded port (commonly `8501`).

The map uses online CartoDB Positron tiles through Folium and requires browser internet access. The rest of the workflow can be demonstrated using the default synthetic records.

## Google AI configuration

1. Create a key from [Google AI Studio](https://aistudio.google.com/apikey).
2. Set `GEMINI_API_KEY` in your environment or add it as a Streamlit secret.
3. In the left sidebar, choose **Gemini API** or **Gemma API**, then select an enabled model ID.

Windows PowerShell:

```powershell
$env:GEMINI_API_KEY="YOUR_KEY_HERE"
python -m streamlit run app.py
```

macOS/Linux:

```bash
export GEMINI_API_KEY="YOUR_KEY_HERE"
python -m streamlit run app.py
```

For Streamlit Community Cloud, add `GEMINI_API_KEY` under **Settings → Secrets**. Never commit an actual key, `.env` file or Streamlit secrets file. API availability, model IDs and quotas depend on your account; use a currently enabled ID if a default is unavailable.

## Public demo walkthrough (90–120 seconds)

1. Open **Overview** and point out the priority queue and Leaflet map; clarify that the preloaded cases are synthetic and pins are approximate sector centroids.
2. Open **New report**. Enter: “A public bin is overflowing beside a pedestrian crossing and waste is spreading onto the walkway.” Select Sector 17, optionally attach a photo, and click **Analyse and prepare draft**.
3. Review the department, severity, first action and possible related reports. Explain that Demo rules are keyword-based; rerun with a Google AI model if configured to demonstrate model inference.
4. Click **Create work order and add to queue**. Show the new case in **Dispatch**, assign a crew and show the team run sheet.
5. Open **Incidents** and show search/filter, case details and CSV export.
6. Open **Verify closure** to show before/after evidence and the human approval checkpoint. Do not claim image comparison ran unless using a configured model.
7. Finish on **Insights**, noting that a real pilot would require authorized municipal data integration and production controls.

## Prototype boundaries

- Seed incidents are synthetic and session-based; they reset when the Streamlit session resets.
- Sector map pins use approximate sector-centroid coordinates. They are not exact citizen GPS positions.
- The map displays locations only. It does **not** calculate a street-following route, live traffic, optimized dispatch or arrival-time estimate.
- Department/severity analysis and priority are suggestions. The demo rules are not a trained classifier; Google AI output can also be wrong.
- No official Chandigarh Administration / Municipal Corporation integration, emergency service connection, user authentication, role separation, notification workflow or audit service is included.
- Before production: connect only authorized records, add access controls and audit logging, govern data retention, use precise verified location data, validate the issue taxonomy with civic staff, and evaluate model errors with real operators.

## Architecture

```text
Citizen text + optional photo
            |
            v
       Guided intake
            |
            v
  Demo rules or Google AI model
            |
            v
 Structured draft: category, department, severity, action
            |
            +--> related-report heuristic
            +--> explainable priority score
            +--> searchable work register + Leaflet map
            +--> team assignment + sector run sheet
            +--> before/after evidence --> human closure approval
```

## Repository checklist

- Keep `app.py`, `requirements.txt`, `.streamlit/config.toml`, `README.md` and `LICENSE` in the public repository.
- Do not upload secrets.
- Test with `python -m pip install -r requirements.txt` and `python -m streamlit run app.py` after publishing.
- Verify the hosted deployment and public demo links in a signed-out browser before submitting.

## License

Apache-2.0. Third-party model and API usage remains subject to the provider's own terms and policies.
