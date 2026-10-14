import json
import os
import re
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from io import BytesIO

import pandas as pd
import streamlit as st
from PIL import Image

try:
    from google import genai
except Exception:
    genai = None

APP_TITLE = "CivicFlow AI"
MODELS = {
    "Gemini (multimodal analysis)": "gemini-3.8-flash",
    "Gemma 4 (open-weight model via API)": "gemma-4-26b-a4b-it",
}
SECTORS = [
    "Sector 1", "Sector 2", "Sector 8", "Sector 10", "Sector 15", "Sector 17",
    "Sector 22", "Sector 26", "Sector 34", "Sector 35", "Sector 43", "Sector 46",
    "Sector 52", "Manimajra", "Industrial Area Phase 1", "Industrial Area Phase 2",
]
DEPARTMENTS = [
    "Waste Management", "Roads & Infrastructure", "Street Lighting", "Drainage",
    "Parks & Public Spaces", "Public Safety", "Water Supply", "Other / Needs Review",
]
SEVERITY_ORDER = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}

st.set_page_config(page_title="CivicFlow AI | Chandigarh", page_icon="🏙️", layout="wide")

st.markdown("""
<style>
:root { color-scheme: light; }
.block-container { padding-top: 1.4rem; padding-bottom: 2.6rem; max-width: 1380px; }
.hero { padding: 1.6rem 1.8rem; border-radius: 18px; color: white; background: linear-gradient(120deg,#102a43 0%,#135b68 64%,#0b7a75 100%); margin-bottom: 1.1rem; }
.hero h1 { color: white; margin: 0 0 .35rem 0; font-size: 2.4rem; letter-spacing: -.03em; }
.hero p { color: #d7edf1; margin: 0; font-size: 1.04rem; }
.kpi { padding: 1rem 1.1rem; border: 1px solid #dce5ea; border-radius: 14px; background: #ffffff; }
.kpi-label { color: #526475; font-size: .85rem; margin-bottom: .3rem; }
.kpi-value { color: #102a43; font-weight: 750; font-size: 1.75rem; line-height: 1.2; }
.small-note { color: #617384; font-size: .82rem; }
.section-head { font-size: 1.2rem; font-weight: 750; color: #102a43; margin-bottom: .55rem; }
.pill { display: inline-block; padding: .18rem .55rem; background: #e9f5f3; color: #11655d; border-radius: 999px; font-size: .78rem; font-weight: 650; }
div[data-testid="stMetric"] { border: 1px solid #dce5ea; padding: 12px 14px; border-radius: 14px; background: white; }
</style>
<div class="hero">
  <div style="font-size:.8rem; text-transform:uppercase; letter-spacing:.14em; font-weight:700; margin-bottom:.65rem;">Code for Communities Chandigarh · Civic Services</div>
  <h1>🏙️ CivicFlow AI</h1>
  <p>From citizen report to accountable resolution — a multimodal civic incident operations prototype.</p>
</div>
""", unsafe_allow_html=True)


def demo_incidents():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = [
        {"id":"CF-104", "created":now, "sector":"Sector 17", "category":"Waste Overflow", "description":"Overflowing public bin near a pedestrian crossing; waste is spreading onto the walkway.", "department":"Waste Management", "severity":"High", "safety_risk":True, "affected":80, "priority":84, "status":"Open", "source":"Demo report", "resolution_note":"", "before_image":None},
        {"id":"CF-103", "created":now, "sector":"Sector 17", "category":"Waste Overflow", "description":"Garbage overflowing from the same market-area bin.", "department":"Waste Management", "severity":"High", "safety_risk":False, "affected":35, "priority":69, "status":"Assigned", "source":"Demo report", "resolution_note":"", "before_image":None},
        {"id":"CF-102", "created":now, "sector":"Sector 22", "category":"Road Damage", "description":"Large pothole causing two-wheelers to swerve into moving traffic.", "department":"Roads & Infrastructure", "severity":"Critical", "safety_risk":True, "affected":120, "priority":96, "status":"Open", "source":"Demo report", "resolution_note":"", "before_image":None},
        {"id":"CF-101", "created":now, "sector":"Sector 35", "category":"Streetlight Outage", "description":"Several streetlights are not working on a walkway used after dark.", "department":"Street Lighting", "severity":"Medium", "safety_risk":True, "affected":45, "priority":63, "status":"Resolved", "source":"Demo report", "resolution_note":"Sample row only; no real-world resolution is implied.", "before_image":None},
    ]
    return rows

if "incidents" not in st.session_state:
    st.session_state.incidents = demo_incidents()
if "last_analysis" not in st.session_state:
    st.session_state.last_analysis = None
if "flash_message" not in st.session_state:
    st.session_state.flash_message = ""


def safe_json(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


def offline_analysis(description, image_bytes=None):
    t = (description or "").lower()
    if any(w in t for w in ["garbage", "waste", "bin", "rubbish", "overflow"]):
        category, department = "Waste Overflow", "Waste Management"
    elif any(w in t for w in ["pothole", "road", "crack", "footpath", "pavement"]):
        category, department = "Road Damage", "Roads & Infrastructure"
    elif any(w in t for w in ["light", "lamp", "dark", "streetlight"]):
        category, department = "Streetlight Outage", "Street Lighting"
    elif any(w in t for w in ["drain", "sewer", "waterlogging", "flood"]):
        category, department = "Drainage Issue", "Drainage"
    elif any(w in t for w in ["park", "tree", "bench", "playground"]):
        category, department = "Park / Public Space", "Parks & Public Spaces"
    elif any(w in t for w in ["water", "pipe", "leak"]):
        category, department = "Water Supply Issue", "Water Supply"
    else:
        category, department = "Civic Issue - Review Needed", "Other / Needs Review"
    safety = any(w in t for w in ["traffic", "crossing", "injur", "danger", "dark", "fire", "open drain", "moving vehicles"])
    severity = "Critical" if any(w in t for w in ["accident", "injur", "exposed wire", "fire", "collapse"]) else ("High" if safety or any(w in t for w in ["overflow", "pothole", "blocked", "severe"]) else "Medium")
    if not t.strip() and image_bytes:
        category, department, severity = "Image submitted - needs AI/API review", "Other / Needs Review", "Medium"
    return {"category":category, "department":department, "severity":severity, "safety_risk":bool(safety), "summary":(description or "Image-only report submitted for review")[:180], "recommended_action":"Inspect the location, document the issue, and assign an accountable field team.", "confidence_note":"Offline keyword-based demo only; not a trained classifier or a factual safety assessment."}


def ai_analysis(description, sector, image_bytes, model_name, api_key):
    if genai is None:
        raise RuntimeError("The google-genai package is not installed. Install requirements.txt first.")
    if not api_key:
        raise RuntimeError("No Gemini API key found. Add GEMINI_API_KEY to your environment or Streamlit secrets, or select Offline demo.")
    client = genai.Client(api_key=api_key)
    prompt = f'''You are assisting a municipal civic-service triage prototype for Chandigarh, India. Analyze the citizen report and optional image. Do not identify people, infer a person's identity, or make claims beyond visible evidence. Prioritize immediate physical hazards conservatively. Return ONLY valid JSON with keys: category (short label), department (choose one of {DEPARTMENTS}), severity (Low, Medium, High, or Critical), safety_risk (boolean), summary (max 35 words), recommended_action (max 45 words), confidence_note (one sentence explaining uncertainty).\nLocation: {sector}\nCitizen text: {description or "No text supplied; analyze the image if present."}'''
    contents = [prompt]
    if image_bytes:
        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            contents.append(image)
        except Exception as exc:
            raise RuntimeError(f"Could not read the uploaded image: {exc}") from exc
    response = client.models.generate_content(model=model_name, contents=contents)
    result = safe_json(response.text)
    result["category"] = str(result.get("category", "Civic Issue"))[:60]
    if result.get("department") not in DEPARTMENTS:
        result["department"] = "Other / Needs Review"
    if result.get("severity") not in SEVERITY_ORDER:
        result["severity"] = "Medium"
    result["safety_risk"] = bool(result.get("safety_risk", False))
    result["summary"] = str(result.get("summary", "Review report"))[:250]
    result["recommended_action"] = str(result.get("recommended_action", "Inspect and assign to a field team."))[:400]
    return result


def priority_score(severity, affected, safety, description):
    score = {"Low": 20, "Medium": 42, "High": 66, "Critical": 82}.get(severity, 42)
    score += min(int(affected or 0) // 10, 12)
    score += 12 if safety else 0
    if any(w in (description or "").lower() for w in ["crossing", "school", "hospital", "blocked road"]):
        score += 5
    return min(100, int(score))


def get_matches(new_description, sector, category):
    matches = []
    new_tokens = set(re.findall(r"[a-z]{3,}", (new_description or "").lower()))
    for item in st.session_state.incidents:
        if item.get("sector") != sector or item.get("status") == "Resolved":
            continue
        same_category = item.get("category", "").lower() == (category or "").lower()
        old_tokens = set(re.findall(r"[a-z]{3,}", (item.get("description") or "").lower()))
        similarity = len(new_tokens & old_tokens) / max(1, len(new_tokens | old_tokens))
        if same_category or similarity >= 0.28:
            matches.append(item)
    return matches


def run_verification(before_bytes, after_bytes, model_name, api_key):
    if not api_key or genai is None:
        return {"status":"Manual review required", "confidence":"Not calculated", "explanation":"API analysis was not run. A human reviewer must compare the evidence before closing the incident."}
    client = genai.Client(api_key=api_key)
    before = Image.open(BytesIO(before_bytes)).convert("RGB")
    after = Image.open(BytesIO(after_bytes)).convert("RGB")
    prompt = '''Compare the BEFORE and AFTER images for a civic maintenance issue. Return only JSON with keys: status (one of Resolved, Partially resolved, Still unresolved, Inconclusive), confidence (Low, Medium, High), explanation (max 45 words). Do not claim certainty if framing, lighting, or image quality prevents comparison. This is assistance for a human reviewer, not final proof.'''
    result = safe_json(client.models.generate_content(model=model_name, contents=[prompt, "BEFORE image:", before, "AFTER image:", after]).text)
    return {"status":str(result.get("status", "Inconclusive")), "confidence":str(result.get("confidence", "Low")), "explanation":str(result.get("explanation", "Human review needed."))}

# Sidebar configuration
with st.sidebar:
    st.markdown("### ⚙️ Prototype settings")
    mode = st.radio("AI mode", ["Offline demo", "Gemini API", "Gemma 4 API"], index=0,
                    help="Offline demo uses transparent keyword rules. Gemini/Gemma modes call the selected Google model.")
    env_key = os.getenv("GEMINI_API_KEY", "")
    secret_key = ""
    try:
        secret_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        pass
    api_key = secret_key or env_key
    if mode != "Offline demo":
        api_key = st.text_input("Google AI API key", value=api_key, type="password", help="A temporary input is kept for this session only. Prefer environment variables / Streamlit secrets.")
        model_name = MODELS["Gemma 4 (open-weight model via API)"] if mode == "Gemma 4 API" else MODELS["Gemini (multimodal analysis)"]
        st.caption(f"Selected model: `{model_name}`")
    else:
        model_name = MODELS["Gemini (multimodal analysis)"]
        st.info("Offline demo mode is useful for walkthroughs. It is not an AI model and should not be presented as model inference.")
    st.divider()
    st.markdown("**Data notice**")
    st.caption("Preloaded incidents are synthetic examples. This prototype is not connected to Chandigarh municipal systems, emergency services, live maps, or official records.")
    if st.button("Reset to sample data", use_container_width=True):
        st.session_state.incidents = demo_incidents()
        st.session_state.last_analysis = None
        st.rerun()

if st.session_state.flash_message:
    st.success(st.session_state.flash_message)
    st.session_state.flash_message = ""

page = st.radio("Workspace", ["Overview", "Report a civic issue", "Field operations", "Resolution verification"], horizontal=True, label_visibility="collapsed")

if page == "Overview":
    rows = st.session_state.incidents
    open_rows = [r for r in rows if r["status"] != "Resolved"]
    critical = sum(1 for r in open_rows if r["severity"] == "Critical")
    assigned = sum(1 for r in open_rows if r["status"] == "Assigned")
    resolved = sum(1 for r in rows if r["status"] == "Resolved")
    a,b,c,d = st.columns(4)
    for col, label, value in [(a,"Open incidents",len(open_rows)),(b,"Critical priority",critical),(c,"Assigned to teams",assigned),(d,"Resolved (sample/session)",resolved)]:
        with col:
            st.markdown(f'<div class="kpi"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div></div>', unsafe_allow_html=True)
    st.write("")
    left, right = st.columns([1.45, 1])
    with left:
        st.markdown('<div class="section-head">Incident queue</div>', unsafe_allow_html=True)
        view_rows = sorted(rows, key=lambda x: (x["status"] == "Resolved", -x["priority"]))
        df = pd.DataFrame([{ "ID":r["id"], "Sector":r["sector"], "Issue":r["category"], "Severity":r["severity"], "Priority":r["priority"], "Department":r["department"], "Status":r["status"] } for r in view_rows])
        st.dataframe(df, use_container_width=True, hide_index=True)
    with right:
        st.markdown('<div class="section-head">Where attention is needed</div>', unsafe_allow_html=True)
        if open_rows:
            counts = pd.DataFrame(open_rows).groupby("sector").size().reset_index(name="Open incidents").sort_values("Open incidents", ascending=False)
            st.bar_chart(counts.set_index("sector"))
        else:
            st.info("No open reports in this session.")
        st.markdown("<div class='small-note'>Prototype analytics only; no live city feed. Priority is a transparent heuristic, not an official municipal SLA.</div>", unsafe_allow_html=True)
    st.divider()
    st.markdown("#### How CivicFlow works")
    flow = st.columns(5)
    stages = [("01 · Capture","Text report + optional photo"),("02 · Understand","Gemini / Gemma analysis"),("03 · Triage","Category, risk, priority"),("04 · Dispatch","Group by sector + team"),("05 · Verify","Before/after review")]
    for col, (heading, desc) in zip(flow, stages):
        with col:
            st.markdown(f"**{heading}**")
            st.caption(desc)

elif page == "Report a civic issue":
    st.markdown("### Submit a report")
    st.write("Create one usable work item from a citizen description and optional visual evidence.")
    with st.form("report_form", clear_on_submit=False):
        f1, f2 = st.columns(2)
        sector = f1.selectbox("Location / sector", SECTORS, index=5)
        affected = f2.number_input("Estimated people affected", min_value=1, max_value=100000, value=30, step=5)
        description = st.text_area("What happened?", placeholder="Example: A public bin is overflowing beside a pedestrian crossing...", height=120)
        uploaded = st.file_uploader("Add a photo (optional)", type=["png", "jpg", "jpeg", "webp"])
        submitted = st.form_submit_button("Analyse report", type="primary", use_container_width=True)
    if submitted:
        photo_bytes = uploaded.getvalue() if uploaded else None
        if not description.strip() and not photo_bytes:
            st.error("Enter a description or attach a photo.")
        else:
            try:
                if mode == "Offline demo":
                    analysis = offline_analysis(description, photo_bytes)
                else:
                    analysis = ai_analysis(description, sector, photo_bytes, model_name, api_key)
                analysis["sector"] = sector
                analysis["affected"] = int(affected)
                analysis["description"] = description.strip() or analysis.get("summary", "Image-only report")
                analysis["photo_bytes"] = photo_bytes
                analysis["matches"] = get_matches(analysis["description"], sector, analysis.get("category", ""))
                st.session_state.last_analysis = analysis
            except Exception as exc:
                st.error(f"Analysis failed: {exc}")
    analysis = st.session_state.last_analysis
    if analysis:
        st.divider()
        st.markdown("### Analysis result")
        if mode == "Offline demo":
            st.warning("Offline demo result: keyword rules only. Select Gemini API or Gemma 4 API to run model inference.")
        ai1, ai2, ai3 = st.columns(3)
        ai1.metric("Detected category", analysis.get("category", "Civic issue"))
        ai2.metric("Recommended department", analysis.get("department", "Review"))
        ai3.metric("Suggested severity", analysis.get("severity", "Medium"))
        st.write(analysis.get("summary", ""))
        st.info(f"Recommended action: {analysis.get('recommended_action', 'Inspect and assign for review.')}")
        st.caption(analysis.get("confidence_note", "AI output needs human review."))
        matches = analysis.get("matches", [])
        st.markdown(f"**Potential related reports:** {len(matches)} in the same sector / with matching category or text. This is a candidate match, not a confirmed duplicate.")
        if matches:
            st.dataframe(pd.DataFrame([{ "ID":m["id"], "Issue":m["category"], "Sector":m["sector"], "Status":m["status"] } for m in matches]), use_container_width=True, hide_index=True)
        if st.button("Create incident & add to queue", type="primary", use_container_width=True):
            new_id = "CF-" + uuid.uuid4().hex[:5].upper()
            severity = analysis.get("severity", "Medium")
            newrow = {"id":new_id, "created":datetime.now().strftime("%Y-%m-%d %H:%M"), "sector":analysis["sector"], "category":analysis.get("category", "Civic issue"), "description":analysis["description"], "department":analysis.get("department", "Other / Needs Review"), "severity":severity, "safety_risk":analysis.get("safety_risk", False), "affected":analysis["affected"], "priority":priority_score(severity, analysis["affected"], analysis.get("safety_risk", False), analysis["description"]), "status":"Open", "source":"Citizen prototype", "resolution_note":"", "before_image":analysis.get("photo_bytes")}
            st.session_state.incidents.insert(0, newrow)
            st.session_state.last_analysis = None
            st.session_state.flash_message = f"Incident {new_id} created. It is now visible in the operations queue."
            st.rerun()

elif page == "Field operations":
    st.markdown("### Field operations")
    st.write("Assign a responsible department and group open work by sector. The route preview is an area-grouping heuristic, not live navigation.")
    pending = [r for r in st.session_state.incidents if r["status"] != "Resolved"]
    if not pending:
        st.info("No open incidents to dispatch.")
    else:
        options = [f'{r["id"]} · {r["category"]} · {r["sector"]}' for r in pending]
        selected_label = st.selectbox("Select incident", options)
        selected = pending[options.index(selected_label)]
        with st.form("dispatch_form"):
            dept = st.selectbox("Assign department", DEPARTMENTS, index=DEPARTMENTS.index(selected["department"]) if selected["department"] in DEPARTMENTS else len(DEPARTMENTS)-1)
            team = st.selectbox("Field team", ["Team A", "Team B", "Team C", "Needs supervisor review"])
            new_status = st.selectbox("Status", ["Open", "Assigned"], index=1 if selected["status"] == "Assigned" else 0)
            do_assign = st.form_submit_button("Save assignment", type="primary")
        if do_assign:
            selected["department"] = dept
            selected["team"] = team
            selected["status"] = new_status
            st.session_state.flash_message = f'{selected["id"]} updated: {new_status} / {team}.'
            st.rerun()
        st.divider()
        st.markdown("#### Route grouping preview")
        assigned = [r for r in pending if r.get("status") == "Assigned"]
        if assigned:
            route = {}
            for r in sorted(assigned, key=lambda z: (-z["priority"], z["sector"])):
                route.setdefault(r.get("team", "Unassigned"), {}).setdefault(r["sector"], []).append(r)
            for team_name, sectors in route.items():
                st.markdown(f"**{team_name}**")
                for i, (sector_name, incident_list) in enumerate(sectors.items(), start=1):
                    items = ", ".join(x["id"] for x in incident_list)
                    st.write(f"{i}. {sector_name} — {len(incident_list)} incident(s): {items}")
        else:
            st.info("Assign an incident to preview a grouped field workload.")
        st.caption("Production extension: connect authorized municipal task records and a road-network route optimizer. No ETA or real road route is calculated here.")
        st.divider()
        st.markdown("#### Current work queue")
        st.dataframe(pd.DataFrame([{ "ID":r["id"], "Priority":r["priority"], "Sector":r["sector"], "Department":r["department"], "Team":r.get("team", "Unassigned"), "Status":r["status"] } for r in sorted(pending, key=lambda z:-z["priority"])]), use_container_width=True, hide_index=True)

else:
    st.markdown("### Resolution verification")
    st.write("Compare before/after photos as decision support. A municipal officer should review the result before closing the work order.")
    all_items = [r for r in st.session_state.incidents if r["status"] != "Resolved"]
    if not all_items:
        st.info("There are no open incidents available for verification.")
    else:
        item_label = st.selectbox("Incident", [f'{r["id"]} · {r["category"]} · {r["sector"]}' for r in all_items])
        item = all_items[[f'{r["id"]} · {r["category"]} · {r["sector"]}' for r in all_items].index(item_label)]
        before_col, after_col = st.columns(2)
        with before_col:
            st.markdown("**Before evidence**")
            if item.get("before_image"):
                st.image(item["before_image"], use_container_width=True)
            else:
                st.warning("No before photo stored for this incident. Uploading one below helps the reviewer, but an actual comparison needs both images.")
                before_upload = st.file_uploader("Upload before photo", type=["png", "jpg", "jpeg", "webp"], key="before_upload")
        with after_col:
            st.markdown("**After evidence**")
            after_upload = st.file_uploader("Upload after photo", type=["png", "jpg", "jpeg", "webp"], key="after_upload")
            if after_upload:
                st.image(after_upload, use_container_width=True)
        if st.button("Compare resolution evidence", type="primary", use_container_width=True):
            before_bytes = item.get("before_image")
            if not before_bytes:
                before_bytes = before_upload.getvalue() if 'before_upload' in locals() and before_upload else None
            after_bytes = after_upload.getvalue() if after_upload else None
            if not before_bytes or not after_bytes:
                st.error("Both before and after photos are required for comparison.")
            else:
                try:
                    if mode == "Offline demo":
                        result = {"status":"Manual review required", "confidence":"Not calculated", "explanation":"Offline mode does not compare images. Choose Gemini API or Gemma 4 API for visual comparison, then have a human reviewer confirm."}
                    else:
                        result = run_verification(before_bytes, after_bytes, model_name, api_key)
                    st.session_state["verification_result"] = result
                    st.session_state["verification_incident_id"] = item["id"]
                    st.session_state["verification_before_bytes"] = before_bytes
                except Exception as exc:
                    st.error(f"Verification failed: {exc}")
        if st.session_state.get("verification_incident_id") == item["id"] and st.session_state.get("verification_result"):
            result = st.session_state["verification_result"]
            st.markdown("#### Model-assisted review")
            st.metric("Suggested status", result["status"])
            st.metric("Confidence", result["confidence"])
            st.write(result["explanation"])
            st.caption("This is decision support, not authoritative proof. Human confirmation is required before closure.")
            if st.button("Mark resolved after human review", type="primary"):
                item["status"] = "Resolved"
                item["resolution_note"] = result["explanation"]
                st.session_state.flash_message = f'{item["id"]} marked resolved after manual confirmation.'
                st.session_state["verification_result"] = None
                st.session_state["verification_incident_id"] = None
                st.rerun()

st.divider()
st.caption("CivicFlow AI is a hackathon prototype. Synthetic sample records are provided for demonstration; AI results may be wrong and require human review. Not an official Chandigarh Administration or Municipal Corporation service.")
