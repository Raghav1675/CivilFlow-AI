# CivicFlow AI — Code for Communities Chandigarh 2026

**Track:** Civic Services  
**One-line pitch:** Turn fragmented citizen complaints into prioritized, assigned, and human-verified civic work orders.

CivicFlow AI is a hackathon prototype for a reusable municipal incident-operations layer. A citizen or operator enters a civic issue and can attach a photo. A Google AI model (Gemini or Gemma 4) can structure the report, suggest a department and severity, and describe an initial response. Operators can triage the work queue, group work by sector/team, and compare before/after photos as decision support for a human resolution review.

> **Prototype boundary:** The app is not connected to Chandigarh municipal systems, official complaint feeds, emergency services, live maps, or road-network routing. Preloaded cases are synthetic examples. Sector grouping is a demonstration heuristic, not navigation or a travel-time estimate. AI analysis can be wrong and must be reviewed by a person.

## What works in this prototype

- Citizen intake: text description, sector, estimated people affected, optional image.
- Model-assisted structured triage using Gemini or Gemma 4 through the Google GenAI SDK.
- Offline demo mode with transparent keyword rules so the flow can be shown without credentials. It is explicitly labelled as non-AI.
- Candidate duplicate / related-report matching based on sector, category, and text overlap.
- Operations dashboard with severity, priority heuristic, status, and department.
- Department/team assignment and a by-sector workload preview.
- Optional before/after image comparison through a configured Google AI model, with a human confirmation step before closing an incident.
- Apache-2.0 license for reuse and extension.

## Run locally

Python 3.10+ is recommended.

```bash
python -m venv .venv
# Windows PowerShell
.venv\\Scripts\\Activate.ps1
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit. In the left sidebar, select **Offline demo** to walk through the flow without an API key.

## Use Google AI

1. Create an API key in Google AI Studio: https://aistudio.google.com/apikey
2. Set an environment variable before starting the app:

   **Windows PowerShell**
   ```powershell
   $env:GEMINI_API_KEY="YOUR_KEY_HERE"
   streamlit run app.py
   ```

   **macOS/Linux**
   ```bash
   export GEMINI_API_KEY="YOUR_KEY_HERE"
   streamlit run app.py
   ```

3. Select **Gemini API** or **Gemma 4 API** in the sidebar. The app uses `gemini-3.8-flash` for Gemini or `gemma-4-26b-a4b-it` for Gemma 4. Model availability and quotas depend on the API account and may change. If a selected model is not enabled for your account, choose another available model.
4. Never commit the real API key. `.env.example` contains only a placeholder.

For Streamlit Community Cloud, add `GEMINI_API_KEY` under the app's **Settings → Secrets**. Keep it out of source files and screenshots.

## Public repository and deployment checklist

1. Create a **public** GitHub repository named `civicflow-ai` (or another name you prefer).
2. Upload the contents of this folder, including `LICENSE`, `README.md`, `requirements.txt`, `app.py`, and `.streamlit/config.toml`. Do not upload a real `.env` file or key.
3. In Streamlit Community Cloud, choose **Create app**, select the repository and `app.py`, then deploy.
4. Add the API key as a Streamlit secret if you want real model inference in the hosted demo. Test the hosted URL in a private/incognito window.
5. Record a 90–120 second demo with voiceover, upload to YouTube as **Unlisted** or Google Drive with **Anyone with the link — Viewer**, and test the link from a signed-out window.
6. Paste the real public demo URL and repository URL into the event form, and upload `CivicFlow_AI_Presentation.pdf`.

## Demo flow (about 2 minutes)

1. Start on Overview and mention that the default incidents are synthetic sample data.
2. Open **Report a civic issue**. Enter: “A public bin is overflowing beside a pedestrian crossing and waste is spreading onto the walkway.” Choose Sector 17; optionally add an image. Run Gemini/Gemma analysis if your key is configured, or demonstrate Offline demo while clearly labelling it.
3. Review the detected category, department, severity, safety flag, action recommendation and candidate related reports. Create the incident.
4. Open **Field operations**, assign it to a team, and show the incident queue / grouped workload preview.
5. Open **Resolution verification** and show the before/after review flow. For a full AI comparison, both photos and an API key are needed; state that a human must approve closure.
6. Finish on the dashboard and explain that a production pilot would connect authorized municipal records and a real road-network route optimizer.

## Architecture

```text
Citizen text + optional image
            |
            v
  Gemini / Gemma 4 analysis (optional API)
            |
            v
 Structured incident: category, department, severity, action
            |
            +--> candidate duplicate matching
            +--> transparent priority heuristic
            +--> operator queue + sector/team grouping
            +--> before/after review --> human confirmation
```

## Current limits and next steps

- Session-based state; records reset when the app session resets. Add a governed database for a pilot.
- No live municipal integration or authentication / role separation yet.
- Related-report matching is a lightweight heuristic, not a semantic embedding index.
- No real map display, road-network routing, live traffic, or ETA.
- AI suggestions need human review; do not use this demo to dispatch emergency services or make decisions about people.
- Pilot plan: validate issue taxonomy with a municipal department, add access controls and audit logs, connect only authorized ticket data, and evaluate false positives / missed hazards before deployment.

## License

Apache-2.0. Third-party model and API usage remains subject to the provider's separate terms and policies.
