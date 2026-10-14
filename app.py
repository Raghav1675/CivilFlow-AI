from __future__ import annotations

import html
import json
import os
import re
import uuid
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from io import BytesIO
from typing import Any

import folium
import pandas as pd
import streamlit as st
from folium.plugins import Fullscreen, MarkerCluster
from PIL import Image
from streamlit_folium import st_folium

try:
    from google import genai
except Exception:  # Google AI is optional when running the demo rules
    genai = None

APP_TITLE = "CivicFlow"
CITY_CENTER = (30.7333, 76.7794)
NAV_ITEMS = ["Overview", "Incidents", "New report", "Dispatch", "Verify closure", "Insights"]
DEPARTMENTS = [
    "Waste Management",
    "Roads & Infrastructure",
    "Street Lighting",
    "Drainage",
    "Parks & Public Spaces",
    "Public Safety",
    "Water Supply",
    "Other / Needs Review",
]
TEAMS = ["North Crew", "Central Crew", "South Crew", "Rapid Response", "Supervisor Review"]
SEVERITY_ORDER = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
SEVERITY_COLOURS = {
    "Low": "#64748b",
    "Medium": "#b7791f",
    "High": "#d05a36",
    "Critical": "#a82a2a",
}
STATUS_COLOURS = {
    "Open": ("#fff0e8", "#a84526"),
    "Assigned": ("#eaf1ff", "#315aa8"),
    "In progress": ("#e7f6ef", "#226a49"),
    "Resolved": ("#e8f4ed", "#2a6545"),
}

# These are illustrative sector centroids for a prototype map, not street-level incident coordinates.
SECTOR_COORDS = {
    "Sector 1": (30.7445, 76.7913),
    "Sector 2": (30.7425, 76.7878),
    "Sector 8": (30.7440, 76.7860),
    "Sector 10": (30.7482, 76.7781),
    "Sector 15": (30.7570, 76.7744),
    "Sector 17": (30.7419, 76.7823),
    "Sector 22": (30.7312, 76.7757),
    "Sector 26": (30.7296, 76.8005),
    "Sector 34": (30.7167, 76.7584),
    "Sector 35": (30.7136, 76.7504),
    "Sector 43": (30.7030, 76.7651),
    "Sector 46": (30.6947, 76.7495),
    "Sector 52": (30.6865, 76.7558),
    "Manimajra": (30.7055, 76.8191),
    "Industrial Area Phase 1": (30.7069, 76.8010),
    "Industrial Area Phase 2": (30.7005, 76.8050),
}
SECTORS = list(SECTOR_COORDS.keys())

st.set_page_config(
    page_title="CivicFlow | Chandigarh Operations",
    page_icon="C",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
    :root {
      --ink: #1c2e29; --muted: #64736d; --paper: #f5f6f2; --white: #ffffff;
      --line: #e0e5df; --green: #1f5a48; --green-dark: #174638;
      --soft-green: #e8f1eb; --orange: #c6653b; --soft-orange: #fbefe7;
    }
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .stApp { background: var(--paper); color: var(--ink); }
    [data-testid="stHeader"] { background: rgba(245,246,242,.92); }
    .block-container { max-width: 1560px; padding-top: 1.45rem; padding-bottom: 3rem; }
    [data-testid="stSidebar"] { background: #1c302a; border-right: 1px solid #28433a; }
    [data-testid="stSidebar"] * { color: #eef4ee; }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #c4d2c9; }
    [data-testid="stSidebar"] hr { border-color: #355047; }
    [data-testid="stSidebar"] [data-testid="stRadio"] > label { color: #aebfb5; font-size: .73rem; text-transform: uppercase; letter-spacing: .13em; font-weight: 700; }
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] { gap: .28rem; }
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label {
      padding: .5rem .62rem; border-radius: 7px; margin: 0; transition: background .15s ease;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:hover { background: #29483c; }
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label p { color: #ecf3ed; font-size: .91rem; }
    [data-testid="stSidebar"] [data-testid="stRadio"] input:checked + div { color: white; }
    .brand-lockup { display:flex; gap: .72rem; align-items:center; margin: .25rem 0 1.25rem 0; }
    .brand-mark { width:40px;height:40px;border-radius:9px;background:#dce9df;color:#1b4436;display:flex;align-items:center;justify-content:center;font-family:Manrope;font-size:1.1rem;font-weight:800;letter-spacing:-.06em; }
    .brand-name { font-family:Manrope;font-size:1.1rem;font-weight:800;letter-spacing:-.045em;color:#fff;line-height:1.1; }
    .brand-sub { font-size:.68rem;color:#afc3b6;letter-spacing:.12em;text-transform:uppercase;margin-top:.25rem; }
    .workspace-note { font-size:.78rem; line-height:1.55; color:#b9cbbf; padding:.8rem; border:1px solid #355047;border-radius:8px;background:#21382f; }
    .eyebrow { color:#63746b; font-size:.70rem; text-transform:uppercase; letter-spacing:.14em; font-weight:700; margin-bottom:.45rem; }
    .page-title { font-family:Manrope,sans-serif; font-size:2.05rem; line-height:1.12; font-weight:800; letter-spacing:-.06em; color:#1b3029; margin:0 0 .4rem 0; }
    .page-subtitle { color:#65746c; font-size:.95rem; margin:0; max-width:840px; line-height:1.55; }
    .page-rule { border:0;border-top:1px solid #dde3dc;margin:1.25rem 0 1.2rem 0; }
    .section-title { font-family:Manrope,sans-serif;font-size:1.05rem;font-weight:800;letter-spacing:-.035em;color:#23382f;margin:0 0 .15rem 0; }
    .section-subtitle { color:#758178;font-size:.82rem;margin-bottom:.8rem;line-height:1.45; }
    .metric-card { background:#fff;border:1px solid var(--line);border-radius:9px;padding:1rem 1.05rem;min-height:117px; }
    .metric-top {display:flex;justify-content:space-between;align-items:center;gap:.5rem;color:#718078;font-size:.79rem;font-weight:600;}
    .metric-number {font-family:Manrope,sans-serif;font-size:2rem;font-weight:800;line-height:1.1;letter-spacing:-.065em;color:#1b3029;margin:.48rem 0 .28rem 0;}
    .metric-foot {color:#87928b;font-size:.73rem;}
    .panel {background:#fff;border:1px solid #e1e6e0;border-radius:10px;padding:1rem 1.1rem;}
    .micro-label {font-size:.68rem;color:#7a887f;text-transform:uppercase;letter-spacing:.13em;font-weight:700;}
    .incident-title {font-family:Manrope,sans-serif;font-weight:800;font-size:.98rem;letter-spacing:-.025em;color:#253a30;}
    .muted {color:#748179;}
    .status-chip {display:inline-flex;align-items:center;gap:.32rem;padding:.22rem .5rem;border-radius:5px;font-size:.72rem;font-weight:700;white-space:nowrap;}
    .sev-chip {display:inline-flex;align-items:center;gap:.32rem;padding:.22rem .5rem;border-radius:5px;font-size:.72rem;font-weight:700;white-space:nowrap;}
    .map-note { color:#79867e;font-size:.73rem;line-height:1.5;margin-top:.45rem; }
    .callout { padding:.85rem .95rem;border-left:3px solid #c6653b;background:#fbf1e9;border-radius:0 7px 7px 0;color:#74452f;font-size:.84rem;line-height:1.5; }
    .step-number { width:27px;height:27px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#e5eee7;color:#225440;font-weight:800;font-size:.76rem;flex-shrink:0; }
    .step-item {display:flex;gap:.6rem;align-items:flex-start;}
    .step-item b {display:block;font-size:.84rem;color:#2a4035;}
    .step-item span {display:block;color:#78857d;font-size:.75rem;line-height:1.4;margin-top:.15rem;}
    div[data-testid="stMetric"] {background:#fff;border:1px solid #e1e6e0;padding:13px 15px;border-radius:9px;}
    div[data-testid="stMetricLabel"] p {color:#718078;font-size:.79rem;}
    div[data-testid="stMetricValue"] {color:#1b3029;font-family:Manrope,sans-serif;font-weight:800;letter-spacing:-.04em;}
    .stButton > button {border-radius:7px;font-weight:700;min-height:2.45rem;border:1px solid #dbe3db;color:#2b4336;background:#fff;transition:all .15s ease;}
    .stButton > button:hover {border-color:#719584;color:#174638;}
    .stButton > button[kind="primary"] {background:#1f5a48;border-color:#1f5a48;color:#fff;}
    .stButton > button[kind="primary"]:hover {background:#174638;border-color:#174638;color:#fff;}
    .stDownloadButton > button {border-radius:7px;font-weight:700;}
    [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea, [data-testid="stSelectbox"] div[data-baseweb="select"] > div, [data-testid="stNumberInput"] input {border-radius:7px;}
    [data-testid="stDataFrame"] {border:1px solid #e1e6e0;border-radius:8px;overflow:hidden;}
    div[data-testid="stForm"] {background:#fff;border:1px solid #e1e6e0;border-radius:10px;padding:1rem 1.1rem;}
    [data-testid="stFileUploader"] section {border-radius:7px;background:#fafbf8;}
    .footer-note {font-size:.73rem;color:#8a958d;border-top:1px solid #dfe4de;margin-top:2rem;padding-top:.85rem;line-height:1.5;}
    @media(max-width:850px){.page-title{font-size:1.7rem}.block-container{padding-left:1rem;padding-right:1rem}.metric-card{min-height:105px}.metric-number{font-size:1.7rem}}
    </style>
    """,
    unsafe_allow_html=True,
)


def now_local() -> datetime:
    return datetime.now().replace(microsecond=0)


def sector_coords(sector: str) -> tuple[float, float]:
    return SECTOR_COORDS.get(sector, CITY_CENTER)


def priority_score(severity: str, affected: int, safety: bool, description: str) -> int:
    score = {"Low": 22, "Medium": 42, "High": 66, "Critical": 82}.get(severity, 42)
    score += min(max(int(affected or 0), 0) // 12, 12)
    score += 12 if safety else 0
    text = (description or "").lower()
    if any(word in text for word in ["crossing", "school", "hospital", "blocked road", "moving traffic"]):
        score += 5
    return max(0, min(100, int(score)))


def demo_incidents() -> list[dict[str, Any]]:
    now = now_local()
    sample = [
        ("CF-2407", 2, "Sector 22", "Road Damage", "Large pothole near a bus stop; two-wheelers are swerving into moving traffic.", "Roads & Infrastructure", "Critical", True, 120, "Open", "", ""),
        ("CF-2406", 5, "Sector 17", "Waste Overflow", "Public bin beside a pedestrian crossing is overflowing onto the walkway.", "Waste Management", "High", True, 80, "Open", "", ""),
        ("CF-2405", 9, "Sector 35", "Streetlight Outage", "Streetlights along a public walkway are not working after dark.", "Street Lighting", "Medium", True, 45, "In progress", "South Crew", ""),
        ("CF-2404", 14, "Sector 26", "Drainage Issue", "A storm drain is blocked and water is collecting around the pavement.", "Drainage", "High", False, 60, "Assigned", "North Crew", ""),
        ("CF-2403", 23, "Sector 15", "Park Maintenance", "A broken bench needs repair in the public park.", "Parks & Public Spaces", "Low", False, 12, "Resolved", "Central Crew", "Sample resolution only; no real-world outcome is implied."),
        ("CF-2402", 31, "Sector 34", "Water Supply Issue", "Water is leaking from a pipe near the footpath.", "Water Supply", "High", False, 55, "Open", "", ""),
        ("CF-2401", 38, "Sector 17", "Waste Overflow", "Garbage is accumulating near the market entrance; the bin may need collection.", "Waste Management", "Medium", False, 35, "Assigned", "Central Crew", ""),
        ("CF-2399", 47, "Sector 43", "Footpath Damage", "Loose paving blocks create a trip hazard near a busy pedestrian route.", "Roads & Infrastructure", "High", True, 50, "Open", "", ""),
        ("CF-2397", 67, "Manimajra", "Streetlight Outage", "A row of streetlights is out near a residential lane.", "Street Lighting", "Medium", False, 28, "Assigned", "North Crew", ""),
        ("CF-2394", 76, "Industrial Area Phase 1", "Waste Overflow", "Mixed waste has been left beside a public collection point.", "Waste Management", "Medium", False, 42, "Resolved", "South Crew", "Sample row only; not a verified municipal closure."),
    ]
    rows: list[dict[str, Any]] = []
    for case_id, age_h, sector, category, desc, department, severity, safety, affected, status, team, resolution in sample:
        lat, lon = sector_coords(sector)
        rows.append({
            "id": case_id,
            "created_at": now - timedelta(hours=age_h),
            "sector": sector,
            "lat": lat,
            "lon": lon,
            "category": category,
            "description": desc,
            "department": department,
            "severity": severity,
            "safety_risk": safety,
            "affected": affected,
            "priority": priority_score(severity, affected, safety, desc),
            "status": status,
            "team": team,
            "source": "Synthetic sample",
            "resolution_note": resolution,
            "before_image": None,
            "after_image": None,
            "updated_at": now - timedelta(hours=max(0, age_h // 3)),
        })
    return rows


def init_state() -> None:
    defaults = {
        "incidents": demo_incidents(),
        "nav": "Overview",
        "selected_incident": None,
        "draft_analysis": None,
        "flash_message": "",
        "verification_result": None,
        "verification_incident_id": None,
        "verification_before_bytes": None,
        "verification_after_bytes": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()


def navigate(page: str) -> None:
    st.session_state.nav = page


def open_incident(incident_id: str) -> None:
    st.session_state.selected_incident = incident_id
    st.session_state.nav = "Incidents"


def reset_demo() -> None:
    st.session_state.incidents = demo_incidents()
    st.session_state.draft_analysis = None
    st.session_state.verification_result = None
    st.session_state.verification_incident_id = None
    st.session_state.flash_message = "Workspace restored to the original synthetic sample cases."
    st.session_state.selected_incident = None


def safe_json(text: str | None) -> dict[str, Any]:
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start:end + 1]
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("The model response was not a JSON object.")
    return value


def offline_analysis(description: str, image_bytes: bytes | None = None) -> dict[str, Any]:
    text = (description or "").lower()
    if any(w in text for w in ["garbage", "waste", "bin", "rubbish", "overflow", "litter"]):
        category, department = "Waste Overflow", "Waste Management"
    elif any(w in text for w in ["pothole", "road", "crack", "footpath", "pavement", "paving"]):
        category, department = "Road Damage", "Roads & Infrastructure"
    elif any(w in text for w in ["light", "lamp", "dark", "streetlight"]):
        category, department = "Streetlight Outage", "Street Lighting"
    elif any(w in text for w in ["drain", "sewer", "waterlogging", "flood", "water collecting"]):
        category, department = "Drainage Issue", "Drainage"
    elif any(w in text for w in ["park", "tree", "bench", "playground"]):
        category, department = "Park / Public Space", "Parks & Public Spaces"
    elif any(w in text for w in ["water", "pipe", "leak"]):
        category, department = "Water Supply Issue", "Water Supply"
    else:
        category, department = "Civic Issue — Review Needed", "Other / Needs Review"
    safety = any(w in text for w in ["traffic", "crossing", "injur", "danger", "dark", "fire", "open drain", "moving vehicle", "trip hazard", "swerve"])
    severity = "Critical" if any(w in text for w in ["accident", "injur", "exposed wire", "fire", "collapse", "electrocution"]) else (
        "High" if safety or any(w in text for w in ["overflow", "pothole", "blocked", "severe", "leak"])
        else "Medium"
    )
    if not text.strip() and image_bytes:
        category, department, severity = "Image submitted — review needed", "Other / Needs Review", "Medium"
    return {
        "category": category,
        "department": department,
        "severity": severity,
        "safety_risk": bool(safety),
        "summary": (description or "Image-only report submitted for review")[:180],
        "recommended_action": "Inspect the location, capture evidence and assign an accountable field team.",
        "confidence_note": "Demo rules only. This is not a trained classifier or an authoritative safety assessment.",
    }


def ai_analysis(description: str, sector: str, image_bytes: bytes | None, model_name: str, api_key: str) -> dict[str, Any]:
    if genai is None:
        raise RuntimeError("Google GenAI SDK is not installed. Run: python -m pip install -r requirements.txt")
    if not api_key:
        raise RuntimeError("No Google AI API key found. Add GEMINI_API_KEY to environment/Streamlit secrets, or use Demo rules.")
    client = genai.Client(api_key=api_key)
    prompt = (
        "You assist with first-pass municipal civic-service triage for Chandigarh, India. Analyze the citizen description "
        "and optional image. Do not identify people or infer personal attributes. Be conservative with claims about safety. "
        f"Return only valid JSON with keys: category (short label), department (choose one of {DEPARTMENTS}), "
        "severity (Low, Medium, High, or Critical), safety_risk (boolean), summary (max 35 words), "
        "recommended_action (max 45 words), confidence_note (one sentence on uncertainty).\n"
        f"Sector: {sector}\nCitizen report: {description or 'No text supplied; inspect the image if present.'}"
    )
    contents: list[Any] = [prompt]
    if image_bytes:
        try:
            contents.append(Image.open(BytesIO(image_bytes)).convert("RGB"))
        except Exception as exc:
            raise RuntimeError(f"Could not read uploaded image: {exc}") from exc
    response = client.models.generate_content(model=model_name, contents=contents)
    result = safe_json(getattr(response, "text", ""))
    result["category"] = str(result.get("category", "Civic issue"))[:60]
    if result.get("department") not in DEPARTMENTS:
        result["department"] = "Other / Needs Review"
    if result.get("severity") not in SEVERITY_ORDER:
        result["severity"] = "Medium"
    result["safety_risk"] = bool(result.get("safety_risk", False))
    result["summary"] = str(result.get("summary", "Review report"))[:250]
    result["recommended_action"] = str(result.get("recommended_action", "Inspect and assign for review."))[:400]
    result["confidence_note"] = str(result.get("confidence_note", "Model output can be wrong; human review required."))[:300]
    return result


def find_matches(description: str, sector: str, category: str, exclude_id: str | None = None) -> list[dict[str, Any]]:
    matches = []
    new_tokens = set(re.findall(r"[a-z]{3,}", (description or "").lower()))
    for incident in st.session_state.incidents:
        if incident.get("id") == exclude_id or incident.get("status") == "Resolved":
            continue
        old_tokens = set(re.findall(r"[a-z]{3,}", (incident.get("description") or "").lower()))
        overlap = len(new_tokens & old_tokens) / max(1, len(new_tokens | old_tokens))
        same_sector_category = incident.get("sector") == sector and incident.get("category", "").lower() == (category or "").lower()
        if same_sector_category or (incident.get("sector") == sector and overlap >= .2) or overlap >= .48:
            matches.append(incident)
    return sorted(matches, key=lambda row: (-row.get("priority", 0), row.get("id", "")))


def run_verification(before_bytes: bytes, after_bytes: bytes, model_name: str, api_key: str) -> dict[str, str]:
    if not api_key or genai is None:
        return {
            "status": "Manual review required",
            "confidence": "Not calculated",
            "explanation": "No model comparison was run. Compare the original and completion photos yourself; the prototype will not infer a result in Demo rules mode.",
        }
    client = genai.Client(api_key=api_key)
    before = Image.open(BytesIO(before_bytes)).convert("RGB")
    after = Image.open(BytesIO(after_bytes)).convert("RGB")
    prompt = (
        "Compare BEFORE and AFTER images for a civic maintenance issue. Return only JSON with keys: status "
        "(Resolved, Partially resolved, Still unresolved, Inconclusive), confidence (Low, Medium, High), "
        "explanation (max 45 words). If the angle, scene, or quality differs too much, use Inconclusive. "
        "This is only a recommendation for a human reviewer, not proof of closure."
    )
    result = safe_json(client.models.generate_content(model=model_name, contents=[prompt, "BEFORE image:", before, "AFTER image:", after]).text)
    valid_status = {"Resolved", "Partially resolved", "Still unresolved", "Inconclusive"}
    valid_conf = {"Low", "Medium", "High"}
    return {
        "status": str(result.get("status", "Inconclusive")) if result.get("status") in valid_status else "Inconclusive",
        "confidence": str(result.get("confidence", "Low")) if result.get("confidence") in valid_conf else "Low",
        "explanation": str(result.get("explanation", "Human review is required."))[:400],
    }


def age_label(created_at: datetime) -> str:
    if not isinstance(created_at, datetime):
        return "—"
    hours = max(0, int((now_local() - created_at).total_seconds() // 3600))
    if hours < 1:
        return "Less than 1h"
    if hours < 24:
        return f"{hours}h"
    days = hours // 24
    return f"{days}d {hours % 24}h"


def severity_badge(severity: str) -> str:
    colour = SEVERITY_COLOURS.get(severity, "#64748b")
    bg = {"Low": "#eef1f2", "Medium": "#fbf3df", "High": "#fff0e8", "Critical": "#fae8e8"}.get(severity, "#eef1f2")
    return f'<span class="sev-chip" style="background:{bg};color:{colour};">{html.escape(severity)}</span>'


def status_badge(status: str) -> str:
    bg, colour = STATUS_COLOURS.get(status, ("#eef1f2", "#53645b"))
    return f'<span class="status-chip" style="background:{bg};color:{colour};">{html.escape(status)}</span>'


def metric_card(label: str, value: Any, foot: str, marker: str = "") -> None:
    marker_html = f'<span style="width:7px;height:7px;background:{marker};border-radius:50%;display:inline-block;"></span>' if marker else ""
    st.markdown(
        f'<div class="metric-card"><div class="metric-top"><span>{html.escape(label)}</span>{marker_html}</div>'
        f'<div class="metric-number">{html.escape(str(value))}</div><div class="metric-foot">{html.escape(foot)}</div></div>',
        unsafe_allow_html=True,
    )


def page_header(eyebrow: str, title: str, subtitle: str, action: str | None = None, target: str | None = None) -> None:
    left, right = st.columns([5, 1.35], vertical_alignment="center")
    with left:
        st.markdown(
            f'<div class="eyebrow">{html.escape(eyebrow)}</div><h1 class="page-title">{html.escape(title)}</h1>'
            f'<p class="page-subtitle">{html.escape(subtitle)}</p>',
            unsafe_allow_html=True,
        )
    if action and target:
        with right:
            st.button(action, type="primary", use_container_width=True, on_click=navigate, args=(target,), key=f"cta_{target}_{title}")
    st.markdown('<hr class="page-rule">', unsafe_allow_html=True)


def section_heading(title: str, subtitle: str | None = None) -> None:
    st.markdown(f'<div class="section-title">{html.escape(title)}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="section-subtitle">{html.escape(subtitle)}</div>', unsafe_allow_html=True)


def render_map(rows: list[dict[str, Any]], key: str, height: int = 440, selected_id: str | None = None) -> None:
    fmap = folium.Map(
        location=CITY_CENTER,
        zoom_start=12,
        tiles="CartoDB positron",
        control_scale=True,
        prefer_canvas=True,
    )
    cluster = MarkerCluster(
        name="Civic incidents",
        options={"showCoverageOnHover": False, "spiderfyOnMaxZoom": True, "maxClusterRadius": 42},
    ).add_to(fmap)
    for row in rows:
        lat = row.get("lat")
        lon = row.get("lon")
        if lat is None or lon is None:
            lat, lon = sector_coords(row.get("sector", ""))
        severity = row.get("severity", "Medium")
        colour = SEVERITY_COLOURS.get(severity, "#64748b")
        radius = 10 if row.get("id") == selected_id else {"Low": 6, "Medium": 7, "High": 8, "Critical": 10}.get(severity, 7)
        incident_id = html.escape(str(row.get("id", "")))
        category = html.escape(str(row.get("category", "Civic incident")))
        sector = html.escape(str(row.get("sector", "Unknown sector")))
        status = html.escape(str(row.get("status", "Open")))
        team = html.escape(str(row.get("team") or "Unassigned"))
        summary = html.escape(str(row.get("description", ""))[:150])
        popup_html = (
            '<div style="font-family:Arial,sans-serif;min-width:210px;color:#20352b;">'
            f'<div style="font-size:11px;color:#6c7b71;margin-bottom:4px;">WORK ORDER {incident_id}</div>'
            f'<div style="font-weight:700;font-size:14px;margin-bottom:5px;">{category}</div>'
            f'<div style="font-size:12px;margin-bottom:7px;">{sector} &nbsp;·&nbsp; {status}</div>'
            f'<div style="font-size:12px;color:#53675a;margin-bottom:7px;">{summary}</div>'
            f'<div style="font-size:11px;color:#6c7b71;">Priority {row.get("priority", 0)}/100 · {team}</div></div>'
        )
        folium.CircleMarker(
            location=(float(lat), float(lon)),
            radius=radius,
            color=colour,
            weight=2,
            fill=True,
            fill_color=colour,
            fill_opacity=.86,
            tooltip=f"{row.get('id')} · {row.get('category')} · {row.get('sector')}",
            popup=folium.Popup(popup_html, max_width=300),
        ).add_to(cluster)
    folium.LayerControl(collapsed=True).add_to(fmap)
    Fullscreen(position="topright", title="Expand map", title_cancel="Exit full screen").add_to(fmap)
    st_folium(fmap, key=key, height=height, use_container_width=True, returned_objects=[])
    st.markdown(
        '<div class="map-note">Map pins use illustrative sector-centroid coordinates, not exact citizen GPS points. The map is interactive, but it does not calculate road routes, live traffic or arrival times. Tiles require an internet connection.</div>',
        unsafe_allow_html=True,
    )


def to_export_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    fields = ["id", "created_at", "sector", "category", "description", "department", "severity", "safety_risk", "affected", "priority", "status", "team", "source", "resolution_note", "updated_at"]
    safe_rows = []
    for row in rows:
        safe_rows.append({field: row.get(field, "") for field in fields})
    return pd.DataFrame(safe_rows, columns=fields)


def unresolved_rows() -> list[dict[str, Any]]:
    return [row for row in st.session_state.incidents if row.get("status") != "Resolved"]


# Sidebar: workspace navigation and configuration
with st.sidebar:
    st.markdown(
        '<div class="brand-lockup"><div class="brand-mark">CF</div><div><div class="brand-name">CivicFlow</div><div class="brand-sub">Chandigarh operations</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="micro-label" style="color:#aebfb5;margin-bottom:.35rem;">Workspace</div>', unsafe_allow_html=True)
    st.radio("Navigate", NAV_ITEMS, key="nav", label_visibility="collapsed")
    st.divider()
    st.markdown('<div class="micro-label" style="color:#aebfb5;margin-bottom:.45rem;">Analysis settings</div>', unsafe_allow_html=True)
    ai_mode = st.selectbox("Analysis engine", ["Demo rules", "Gemini API", "Gemma API"], index=0, help="Demo rules are transparent keyword rules, not model inference.")
    model_name = "gemini-3.8-flash" if ai_mode != "Gemma API" else "gemma-4-26b-a4b-it"
    if ai_mode != "Demo rules":
        model_name = st.text_input("Model ID", value=model_name, help="Use a model ID enabled for your Google AI account.")
    env_key = os.getenv("GEMINI_API_KEY", "")
    try:
        secret_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        secret_key = ""
    api_key = secret_key or env_key
    if ai_mode != "Demo rules":
        api_key = st.text_input("Google AI API key", value=api_key, type="password", help="Prefer environment variables or Streamlit secrets. Never commit the key.")
        st.caption(f"Model endpoint: `{model_name}`")
    else:
        st.markdown('<div class="workspace-note"><b>Demo environment</b><br>Sample records are synthetic. Demo rules can showcase workflow without credentials, but are not AI inference.</div>', unsafe_allow_html=True)
    st.divider()
    st.markdown('<div class="micro-label" style="color:#aebfb5;margin-bottom:.45rem;">Workspace actions</div>', unsafe_allow_html=True)
    st.button("＋  Create new report", use_container_width=True, type="primary", on_click=navigate, args=("New report",))
    st.button("↻  Reset sample cases", use_container_width=True, on_click=reset_demo)
    st.markdown('<div class="workspace-note" style="margin-top:.6rem;">Prototype only. No live Chandigarh municipal feed, official dispatch integration, or verified street-level coordinates.</div>', unsafe_allow_html=True)

if st.session_state.flash_message:
    st.toast(st.session_state.flash_message, icon="✓")
    st.session_state.flash_message = ""

rows = st.session_state.incidents
open_rows = [row for row in rows if row.get("status") != "Resolved"]
critical_rows = [row for row in open_rows if row.get("severity") == "Critical"]
unassigned_rows = [row for row in open_rows if not row.get("team")]
assigned_rows = [row for row in open_rows if row.get("team")]
resolved_rows = [row for row in rows if row.get("status") == "Resolved"]


# -----------------------------------------------------------------------------
# OVERVIEW
# -----------------------------------------------------------------------------
if st.session_state.nav == "Overview":
    today = now_local().strftime("%A, %d %B %Y")
    page_header(
        "City services / Operations desk",
        "Good work starts with a clear picture.",
        f"Chandigarh civic-service workspace · {today}. Review the queue, locate issues by sector, and route the next action.",
        "＋ New report",
        "New report",
    )
    metric_cols = st.columns(4, gap="medium")
    with metric_cols[0]: metric_card("Open work orders", len(open_rows), "Awaiting confirmed closure", "#d05a36")
    with metric_cols[1]: metric_card("Critical attention", len(critical_rows), "Safety-sensitive cases in queue", "#a82a2a")
    with metric_cols[2]: metric_card("Unassigned", len(unassigned_rows), "Need a responsible team", "#b7791f")
    with metric_cols[3]: metric_card("Closed in workspace", len(resolved_rows), "Includes synthetic sample rows", "#3f7e5c")

    st.write("")
    map_col, queue_col = st.columns([1.55, 1], gap="large")
    with map_col:
        section_heading("Incident map", "Clustered work orders across Chandigarh sectors · select a marker for its case summary.")
        render_map(rows, key="overview_incident_map", height=470, selected_id=st.session_state.selected_incident)
        legend = st.columns(4)
        for col, severity in zip(legend, ["Critical", "High", "Medium", "Low"]):
            with col:
                st.markdown(f'{severity_badge(severity)}', unsafe_allow_html=True)
    with queue_col:
        section_heading("Needs attention", "Priority-ranked cases that have not been marked resolved.")
        attention = sorted(open_rows, key=lambda item: (item.get("priority", 0), SEVERITY_ORDER.get(item.get("severity", "Low"), 1)), reverse=True)[:5]
        if not attention:
            st.info("The open queue is clear. New reports will appear here.")
        for item in attention:
            with st.container(border=True):
                head_l, head_r = st.columns([3, 1])
                with head_l:
                    st.markdown(f'<div class="micro-label">{html.escape(item["id"])} · {html.escape(item["sector"])}</div><div class="incident-title">{html.escape(item["category"])}</div>', unsafe_allow_html=True)
                with head_r:
                    st.markdown(f'<div style="text-align:right;font-weight:800;color:#243a30;">{item["priority"]}<span style="font-size:.67rem;color:#7c8981;"> /100</span></div>', unsafe_allow_html=True)
                st.markdown(f'{severity_badge(item["severity"])} &nbsp; {status_badge(item["status"])}', unsafe_allow_html=True)
                st.caption(f'{item.get("team") or "Not assigned"} · Reported {age_label(item["created_at"])} ago')
                st.button("Review work order →", key=f"review_{item['id']}", use_container_width=True, on_click=open_incident, args=(item["id"],))
        if len(open_rows) > 5:
            st.button(f"Open all {len(open_rows)} active cases", use_container_width=True, on_click=navigate, args=("Incidents",))

    st.write("")
    lower_left, lower_right = st.columns([1.1, 1], gap="large")
    with lower_left:
        section_heading("Where workload is building", "Open incidents by service department.")
        if open_rows:
            dept_counts = pd.DataFrame(open_rows).groupby("department").size().reset_index(name="Open work orders").sort_values("Open work orders", ascending=False)
            st.bar_chart(dept_counts.set_index("department"), height=245, horizontal=True)
        else:
            st.info("No active work orders to chart.")
    with lower_right:
        section_heading("From report to resolution", "A workflow designed for accountable human decisions.")
        for n, title, detail in [
            ("01", "Capture", "Collect a plain-language report and optional photo."),
            ("02", "Triage", "Structure the issue, department, priority and related reports."),
            ("03", "Dispatch", "Name a team and group work by sector."),
            ("04", "Verify", "Review completion evidence before an operator closes the case."),
        ]:
            st.markdown(f'<div class="step-item" style="margin:.65rem 0;"><div class="step-number">{n}</div><div><b>{title}</b><span>{detail}</span></div></div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# INCIDENTS REGISTER
# -----------------------------------------------------------------------------
elif st.session_state.nav == "Incidents":
    page_header("Operations / Work register", "Incidents and work orders", "Search the queue, narrow it by service or status, and edit ownership or progress.", "＋ New report", "New report")
    rows = st.session_state.incidents
    f1, f2, f3, f4 = st.columns([1.6, 1, 1, 1.1])
    with f1:
        query = st.text_input("Search", placeholder="ID, description, sector or category", label_visibility="collapsed")
    with f2:
        status_filter = st.selectbox("Status", ["All statuses", "Open", "Assigned", "In progress", "Resolved"], label_visibility="collapsed")
    with f3:
        severity_filter = st.selectbox("Severity", ["All severities", "Critical", "High", "Medium", "Low"], label_visibility="collapsed")
    with f4:
        dept_filter = st.selectbox("Department", ["All departments"] + DEPARTMENTS, label_visibility="collapsed")
    filtered = []
    for item in rows:
        hay = " ".join([item.get("id", ""), item.get("sector", ""), item.get("category", ""), item.get("description", ""), item.get("department", ""), item.get("team", "")]).lower()
        if query and query.lower() not in hay: continue
        if status_filter != "All statuses" and item.get("status") != status_filter: continue
        if severity_filter != "All severities" and item.get("severity") != severity_filter: continue
        if dept_filter != "All departments" and item.get("department") != dept_filter: continue
        filtered.append(item)
    filtered.sort(key=lambda item: (item.get("status") == "Resolved", -item.get("priority", 0)))
    csv_bytes = to_export_frame(filtered).to_csv(index=False).encode("utf-8")
    table_left, table_right = st.columns([1.75, 1], gap="large")
    with table_left:
        section_heading(f"Work register · {len(filtered)} records", "Prioritization is a heuristic to help reviewers; it is not an official municipal SLA.")
        if filtered:
            frame = pd.DataFrame([{
                "ID": item["id"], "Sector": item["sector"], "Issue": item["category"], "Priority": item["priority"],
                "Severity": item["severity"], "Department": item["department"], "Team": item.get("team") or "—", "Status": item["status"],
                "Age": age_label(item["created_at"]),
            } for item in filtered])
            st.dataframe(frame, use_container_width=True, hide_index=True, height=400, column_config={
                "Priority": st.column_config.ProgressColumn("Priority", min_value=0, max_value=100, format="%d/100"),
            })
        else:
            st.info("No work orders match those filters.")
        st.download_button("Export filtered register · CSV", data=csv_bytes, file_name="civicflow_work_register.csv", mime="text/csv", use_container_width=True)
    with table_right:
        section_heading("Work order details", "Choose a record to review or update.")
        if filtered:
            ids = [item["id"] for item in filtered]
            default_id = st.session_state.selected_incident if st.session_state.selected_incident in ids else ids[0]
            selected_id = st.selectbox("Work order", ids, index=ids.index(default_id), format_func=lambda item_id: next((f'{i["id"]} · {i["category"]}' for i in filtered if i["id"] == item_id), item_id))
            selected = next(item for item in filtered if item["id"] == selected_id)
            st.session_state.selected_incident = selected_id
            st.markdown(f'<div class="panel"><div class="micro-label">{html.escape(selected["id"])} · {html.escape(selected["sector"])}</div><div class="incident-title" style="font-size:1.13rem;margin:.3rem 0 .6rem;">{html.escape(selected["category"])}</div>{severity_badge(selected["severity"])} &nbsp; {status_badge(selected["status"])}<p style="color:#68766d;font-size:.86rem;line-height:1.55;margin:.75rem 0 .3rem;">{html.escape(selected["description"])}</p><div style="font-size:.77rem;color:#87928b;">Reported {age_label(selected["created_at"])} ago · {selected["affected"]} estimated people affected</div></div>', unsafe_allow_html=True)
            if selected.get("before_image"):
                st.image(selected["before_image"], caption="Attached intake photo", use_container_width=True)
            with st.form(f"edit_workorder_{selected_id}"):
                edit_a, edit_b = st.columns(2)
                with edit_a:
                    new_status = st.selectbox("Status", ["Open", "Assigned", "In progress", "Resolved"], index=["Open", "Assigned", "In progress", "Resolved"].index(selected["status"]))
                    new_dept = st.selectbox("Department", DEPARTMENTS, index=DEPARTMENTS.index(selected["department"]) if selected["department"] in DEPARTMENTS else len(DEPARTMENTS)-1)
                with edit_b:
                    new_team = st.selectbox("Responsible team", ["Unassigned"] + TEAMS, index=((["Unassigned"] + TEAMS).index(selected.get("team") or "Unassigned")))
                    new_affected = st.number_input("Estimated people affected", min_value=1, max_value=100000, value=int(selected.get("affected", 1)), step=5)
                save_edit = st.form_submit_button("Save work order changes", type="primary", use_container_width=True)
            if save_edit:
                selected["status"] = new_status
                selected["department"] = new_dept
                selected["team"] = "" if new_team == "Unassigned" else new_team
                selected["affected"] = int(new_affected)
                selected["priority"] = priority_score(selected["severity"], selected["affected"], selected["safety_risk"], selected["description"])
                selected["updated_at"] = now_local()
                st.session_state.flash_message = f"{selected_id} has been updated."
                st.rerun()
            action_a, action_b = st.columns(2)
            with action_a:
                st.button("Open on map", key=f"mapfocus_{selected_id}", use_container_width=True, on_click=navigate, args=("Overview",))
            with action_b:
                st.button("Verify closure →", key=f"verify_{selected_id}", use_container_width=True, on_click=navigate, args=("Verify closure",))
        else:
            st.info("Clear some filters to choose a record.")
    st.write("")
    section_heading("Locations", "Use clustered markers to inspect where sample work orders sit across the city.")
    render_map(filtered or rows, key="register_map", height=410, selected_id=st.session_state.selected_incident)

# -----------------------------------------------------------------------------
# NEW REPORT / TRIAGE
# -----------------------------------------------------------------------------
elif st.session_state.nav == "New report":
    page_header("Citizen intake / Create work order", "Start with what happened.", "A short description and a useful location are enough to begin. The system prepares a draft; an operator decides what enters the work queue.")
    left, right = st.columns([1.25, .8], gap="large")
    with left:
        st.markdown('<div class="section-title">01 / Report details</div><div class="section-subtitle">Capture the issue in the reporter\'s own words. Add a photo where it helps.</div>', unsafe_allow_html=True)
        with st.form("new_civic_report", clear_on_submit=False):
            sector = st.selectbox("Location / sector", SECTORS, index=SECTORS.index("Sector 17"))
            affected = st.number_input("Estimated people affected", min_value=1, max_value=100000, value=30, step=5)
            description = st.text_area("Describe the issue", placeholder="Example: A public bin is overflowing beside a pedestrian crossing and waste is spreading onto the walkway.", height=145, max_chars=1400)
            photo_upload = st.file_uploader("Photo evidence (optional)", type=["png", "jpg", "jpeg", "webp"], help="Avoid uploading images containing identifiable people unless necessary and authorized.")
            analyze_clicked = st.form_submit_button("Analyse and prepare draft  →", type="primary", use_container_width=True)
        if analyze_clicked:
            photo_bytes = photo_upload.getvalue() if photo_upload else None
            if not description.strip() and not photo_bytes:
                st.error("Add a description or a photo to continue.")
            else:
                try:
                    with st.spinner("Preparing the triage draft…"):
                        result = offline_analysis(description, photo_bytes) if ai_mode == "Demo rules" else ai_analysis(description, sector, photo_bytes, model_name, api_key)
                    result.update({
                        "sector": sector,
                        "affected": int(affected),
                        "description": description.strip() or result.get("summary", "Image-only report"),
                        "photo_bytes": photo_bytes,
                        "matches": find_matches(description, sector, result.get("category", "")),
                        "engine": ai_mode,
                    })
                    st.session_state.draft_analysis = result
                except Exception as exc:
                    st.error(f"The report could not be analysed: {exc}")
    with right:
        st.markdown('<div class="section-title">02 / Location context</div><div class="section-subtitle">The selected sector is shown on a map so an operator can confirm the broad area.</div>', unsafe_allow_html=True)
        lat, lon = sector_coords(sector if "sector" in locals() else "Sector 17")
        fmap = folium.Map(location=[lat, lon], zoom_start=14, tiles="CartoDB positron", control_scale=True)
        folium.Marker([lat, lon], tooltip=sector if "sector" in locals() else "Sector 17", popup="Approximate sector centre", icon=folium.Icon(color="green", icon="info-sign")).add_to(fmap)
        st_folium(fmap, key="intake_sector_map", height=310, use_container_width=True, returned_objects=[])
        st.markdown('<div class="callout">Sector-level location only. This prototype does not collect precise GPS coordinates or submit a complaint to an official government system.</div>', unsafe_allow_html=True)
        st.write("")
        st.markdown('<div class="panel"><div class="micro-label">What happens next</div><div style="font-size:.87rem;line-height:1.55;color:#66756c;margin-top:.45rem;">Review the category, severity and proposed department. Check possible related reports, then create a work order only when the draft looks reasonable.</div></div>', unsafe_allow_html=True)

    analysis = st.session_state.draft_analysis
    if analysis:
        st.markdown('<hr class="page-rule">', unsafe_allow_html=True)
        st.markdown('<div class="eyebrow">03 / Triage review</div><div class="page-title" style="font-size:1.55rem;">Draft assessment</div>', unsafe_allow_html=True)
        if analysis.get("engine") == "Demo rules":
            st.info("This draft was prepared with transparent keyword rules, not a Google AI model. Switch the analysis engine in the sidebar to run model inference.")
        r1, r2, r3, r4 = st.columns([1, 1.3, 1, 1])
        with r1: metric_card("Suggested priority", f'{priority_score(analysis["severity"], analysis["affected"], analysis["safety_risk"], analysis["description"])} / 100', "Explainable rule-based score", SEVERITY_COLOURS[analysis["severity"]])
        with r2: metric_card("Issue category", analysis["category"], "Operator may correct this", "#3f7e5c")
        with r3: metric_card("Department", analysis["department"], "Suggested owner", "#3f7e5c")
        with r4: metric_card("Severity", analysis["severity"], "Requires human review", SEVERITY_COLOURS[analysis["severity"]])
        st.write(analysis.get("summary", ""))
        st.markdown(f'<div class="panel"><div class="micro-label">Recommended first action</div><div style="font-size:.93rem;color:#2b4135;line-height:1.55;margin-top:.3rem;">{html.escape(analysis.get("recommended_action", "Inspect and assign for review."))}</div><div class="map-note">{html.escape(analysis.get("confidence_note", "Human review required."))}</div></div>', unsafe_allow_html=True)
        possible_matches = analysis.get("matches", [])
        if possible_matches:
            st.warning(f"{len(possible_matches)} possibly related open report(s) found. Confirm whether this is a duplicate before creating another work order.")
            st.dataframe(pd.DataFrame([{"ID": m["id"], "Issue": m["category"], "Sector": m["sector"], "Status": m["status"], "Priority": m["priority"]} for m in possible_matches]), use_container_width=True, hide_index=True)
        create_col, discard_col = st.columns([1.2, 1])
        with create_col:
            if st.button("Create work order and add to queue", type="primary", use_container_width=True):
                lat, lon = sector_coords(analysis["sector"])
                severity = analysis.get("severity", "Medium")
                new_id = "CF-" + uuid.uuid4().hex[:5].upper()
                new_item = {
                    "id": new_id, "created_at": now_local(), "sector": analysis["sector"], "lat": lat, "lon": lon,
                    "category": analysis.get("category", "Civic issue"), "description": analysis["description"],
                    "department": analysis.get("department", "Other / Needs Review"), "severity": severity,
                    "safety_risk": analysis.get("safety_risk", False), "affected": int(analysis["affected"]),
                    "priority": priority_score(severity, analysis["affected"], analysis.get("safety_risk", False), analysis["description"]),
                    "status": "Open", "team": "", "source": "Citizen intake prototype", "resolution_note": "",
                    "before_image": analysis.get("photo_bytes"), "after_image": None, "updated_at": now_local(),
                }
                st.session_state.incidents.insert(0, new_item)
                st.session_state.selected_incident = new_id
                st.session_state.draft_analysis = None
                st.session_state.flash_message = f"Work order {new_id} has been created. Assign a responsible team next."
                st.session_state.nav = "Dispatch"
                st.rerun()
        with discard_col:
            if st.button("Discard draft", use_container_width=True):
                st.session_state.draft_analysis = None
                st.rerun()

# -----------------------------------------------------------------------------
# DISPATCH
# -----------------------------------------------------------------------------
elif st.session_state.nav == "Dispatch":
    page_header("Field operations / Assign work", "Put a name next to the next action.", "Assign a department and team, then use the map and sector run sheet to organise the workday. No live traffic routing is implied.", "View incident queue", "Incidents")
    open_rows = unresolved_rows()
    no_owner = [item for item in open_rows if not item.get("team")]
    team_columns = st.columns(4)
    team_stats = [
        ("Unassigned", len(no_owner), "Needs an owner", "#b7791f"),
        ("North Crew", sum(item.get("team") == "North Crew" for item in open_rows), "Open work orders", "#477b62"),
        ("Central Crew", sum(item.get("team") == "Central Crew" for item in open_rows), "Open work orders", "#477b62"),
        ("South / Rapid / Review", sum(item.get("team") in ["South Crew", "Rapid Response", "Supervisor Review"] for item in open_rows), "Open work orders", "#477b62"),
    ]
    for col, (label, value, foot, marker) in zip(team_columns, team_stats):
        with col: metric_card(label, value, foot, marker)
    st.write("")
    assign_col, run_col = st.columns([.95, 1.25], gap="large")
    with assign_col:
        section_heading("Dispatch a work order", "Set ownership and record the handoff.")
        if not open_rows:
            st.success("No open work orders are waiting for dispatch.")
        else:
            all_ids = [item["id"] for item in sorted(open_rows, key=lambda x: (-x.get("priority", 0), x["id"]))]
            preferred = st.session_state.selected_incident if st.session_state.selected_incident in all_ids else all_ids[0]
            with st.form("dispatch_assignment"):
                chosen_id = st.selectbox("Work order", all_ids, index=all_ids.index(preferred), format_func=lambda item_id: next((f'{i["id"]} · {i["category"]} · {i["sector"]}' for i in open_rows if i["id"] == item_id), item_id))
                chosen = next(item for item in open_rows if item["id"] == chosen_id)
                selected_dept = st.selectbox("Department", DEPARTMENTS, index=DEPARTMENTS.index(chosen["department"]) if chosen["department"] in DEPARTMENTS else len(DEPARTMENTS)-1)
                existing_team = chosen.get("team") or "North Crew"
                selected_team = st.selectbox("Assign to team", TEAMS, index=TEAMS.index(existing_team) if existing_team in TEAMS else 0)
                selected_status = st.selectbox("Set status", ["Assigned", "In progress"], index=1 if chosen["status"] == "In progress" else 0)
                st.caption(f'Priority {chosen["priority"]}/100 · {chosen["severity"]} · {chosen["affected"]} estimated people affected')
                dispatch_submit = st.form_submit_button("Assign team and update queue", type="primary", use_container_width=True)
            if dispatch_submit:
                chosen["department"] = selected_dept
                chosen["team"] = selected_team
                chosen["status"] = selected_status
                chosen["updated_at"] = now_local()
                st.session_state.selected_incident = chosen_id
                st.session_state.flash_message = f"{chosen_id} assigned to {selected_team}."
                st.rerun()
        st.write("")
        section_heading("Dispatch notes", "A short checklist for the field handoff.")
        st.markdown('<div class="step-item" style="margin:.6rem 0;"><div class="step-number">1</div><div><b>Confirm the location</b><span>Sector coordinates are approximate; verify the site before travelling.</span></div></div>', unsafe_allow_html=True)
        st.markdown('<div class="step-item" style="margin:.6rem 0;"><div class="step-number">2</div><div><b>Capture evidence</b><span>Keep the original photo attached to the work order.</span></div></div>', unsafe_allow_html=True)
        st.markdown('<div class="step-item" style="margin:.6rem 0;"><div class="step-number">3</div><div><b>Close with review</b><span>Attach completion evidence and require a human confirmation.</span></div></div>', unsafe_allow_html=True)
    with run_col:
        section_heading("Sector run sheet", "Open assigned work grouped by team and sector, highest priority first.")
        assigned_open = [item for item in open_rows if item.get("team")]
        if assigned_open:
            map_team = st.selectbox("Map layer", ["All assigned teams"] + TEAMS, key="dispatch_map_team")
            map_rows = assigned_open if map_team == "All assigned teams" else [item for item in assigned_open if item.get("team") == map_team]
            render_map(map_rows, key="dispatch_map", height=360)
            run_sheet: list[dict[str, Any]] = []
            for team in TEAMS:
                team_items = sorted([item for item in assigned_open if item.get("team") == team], key=lambda x: (-x.get("priority", 0), x.get("sector", "")))
                if not team_items: continue
                st.markdown(f'**{team}** <span class="muted" style="font-size:.78rem;">· {len(team_items)} open work order(s)</span>', unsafe_allow_html=True)
                by_sector: dict[str, list[dict[str, Any]]] = {}
                for item in team_items:
                    by_sector.setdefault(item["sector"], []).append(item)
                for stop, (sector, incidents_at_sector) in enumerate(by_sector.items(), start=1):
                    ids = ", ".join(item["id"] for item in incidents_at_sector)
                    st.markdown(f'<div style="padding:.45rem .65rem;border:1px solid #e3e8e1;background:#fff;border-radius:6px;margin:.35rem 0;font-size:.82rem;"><span style="color:#7b8980;font-size:.7rem;letter-spacing:.08em;">STOP {stop:02d}</span><br><b>{html.escape(sector)}</b><br><span style="color:#6e7b73;">{html.escape(ids)}</span></div>', unsafe_allow_html=True)
                    run_sheet.extend([{"Team": team, "Stop": stop, "Sector": sector, "Work order": item["id"], "Issue": item["category"], "Priority": item["priority"], "Status": item["status"]} for item in incidents_at_sector])
            run_df = pd.DataFrame(run_sheet)
            st.download_button("Download team run sheet · CSV", data=run_df.to_csv(index=False).encode("utf-8"), file_name="civicflow_team_run_sheet.csv", mime="text/csv", use_container_width=True)
        else:
            st.info("Assign an open work order to see a team map and sector run sheet.")

# -----------------------------------------------------------------------------
# VERIFY CLOSURE
# -----------------------------------------------------------------------------
elif st.session_state.nav == "Verify closure":
    page_header("Quality control / Completion evidence", "Close the loop, not just the ticket.", "Compare intake evidence with the completion photo. Model output is advisory; the operator must make the closure decision.")
    eligible = [item for item in st.session_state.incidents if item.get("status") != "Resolved"]
    if not eligible:
        st.success("There are no open work orders waiting for a closure review.")
    else:
        ids = [item["id"] for item in eligible]
        preferred = st.session_state.selected_incident if st.session_state.selected_incident in ids else ids[0]
        chosen_id = st.selectbox("Select open work order", ids, index=ids.index(preferred), format_func=lambda item_id: next((f'{i["id"]} · {i["category"]} · {i["sector"]}' for i in eligible if i["id"] == item_id), item_id))
        item = next(i for i in eligible if i["id"] == chosen_id)
        st.session_state.selected_incident = chosen_id
        st.markdown(f'<div class="panel"><div class="micro-label">{html.escape(item["id"])} · {html.escape(item["sector"])}</div><div class="incident-title" style="margin:.3rem 0 .5rem;">{html.escape(item["category"])}</div>{severity_badge(item["severity"])} &nbsp; {status_badge(item["status"])}<p style="margin:.65rem 0 .2rem;color:#6d7a72;font-size:.86rem;">{html.escape(item["description"])}</p></div>', unsafe_allow_html=True)
        before_col, after_col = st.columns(2, gap="large")
        with before_col:
            section_heading("Before / intake evidence", "The photo captured when the report was created.")
            if item.get("before_image"):
                st.image(item["before_image"], use_container_width=True)
                replace_before = st.file_uploader("Replace before photo (optional)", type=["png", "jpg", "jpeg", "webp"], key=f"before_{chosen_id}")
            else:
                st.warning("No intake photo was attached to this work order. Upload an original photo if available.")
                replace_before = st.file_uploader("Upload before photo", type=["png", "jpg", "jpeg", "webp"], key=f"before_{chosen_id}")
        with after_col:
            section_heading("After / completion evidence", "Upload a photo taken after the maintenance work.")
            after_upload = st.file_uploader("Upload completion photo", type=["png", "jpg", "jpeg", "webp"], key=f"after_{chosen_id}")
            if after_upload:
                st.image(after_upload, use_container_width=True)
            elif item.get("after_image"):
                st.image(item["after_image"], caption="Previously submitted completion evidence", use_container_width=True)
        if st.button("Compare evidence", type="primary", use_container_width=True):
            before_bytes = replace_before.getvalue() if replace_before else item.get("before_image")
            after_bytes = after_upload.getvalue() if after_upload else item.get("after_image")
            if not before_bytes or not after_bytes:
                st.error("Both a before photo and an after photo are required to run a comparison.")
            else:
                try:
                    with st.spinner("Reviewing the two images…"):
                        verification = run_verification(before_bytes, after_bytes, model_name, api_key) if ai_mode != "Demo rules" else run_verification(before_bytes, after_bytes, "", "")
                    st.session_state.verification_result = verification
                    st.session_state.verification_incident_id = chosen_id
                    st.session_state.verification_before_bytes = before_bytes
                    st.session_state.verification_after_bytes = after_bytes
                except Exception as exc:
                    st.error(f"Evidence comparison failed: {exc}")
        if st.session_state.verification_incident_id == chosen_id and st.session_state.verification_result:
            result = st.session_state.verification_result
            st.write("")
            section_heading("Reviewer assessment", "Treat this as a prompt for inspection, not proof of completion.")
            status_col, conf_col = st.columns(2)
            with status_col: st.metric("Suggested result", result["status"])
            with conf_col: st.metric("Model confidence", result["confidence"])
            st.info(result["explanation"])
            st.markdown('<div class="callout">Before closing the work order, check the photos yourself. Different angles, lighting or a partial repair can make image comparison unreliable.</div>', unsafe_allow_html=True)
            reviewer_note = st.text_area("Human reviewer note", placeholder="What did you verify at the site? What remains to be done?", key=f"review_note_{chosen_id}")
            human_confirm = st.checkbox("I reviewed the evidence and approve closing this work order.", key=f"human_confirm_{chosen_id}")
            if st.button("Confirm resolution and close work order", type="primary", use_container_width=True, disabled=not human_confirm):
                item["before_image"] = st.session_state.verification_before_bytes
                item["after_image"] = st.session_state.verification_after_bytes
                item["status"] = "Resolved"
                item["resolution_note"] = reviewer_note.strip() or result["explanation"]
                item["updated_at"] = now_local()
                st.session_state.flash_message = f"{chosen_id} closed after human confirmation."
                st.session_state.verification_result = None
                st.session_state.verification_incident_id = None
                st.session_state.nav = "Overview"
                st.rerun()

# -----------------------------------------------------------------------------
# INSIGHTS
# -----------------------------------------------------------------------------
elif st.session_state.nav == "Insights":
    page_header("Service intelligence / Workspace analytics", "See what is building up.", "Review the current workspace by issue type, department and priority. All preloaded cases are synthetic; this is not an official city-wide trend report.", "Open work register", "Incidents")
    rows = st.session_state.incidents
    open_rows = [item for item in rows if item.get("status") != "Resolved"]
    all_frame = to_export_frame(rows)
    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("Total reports", len(rows), "Within this session", "#477b62")
    with c2: metric_card("Open / active", len(open_rows), "Not marked resolved", "#d05a36")
    with c3: metric_card("Safety flagged", sum(bool(item.get("safety_risk")) for item in open_rows), "Requires human review", "#a82a2a")
    with c4: metric_card("Assigned", sum(bool(item.get("team")) for item in open_rows), "Has named field team", "#477b62")
    st.write("")
    left, right = st.columns(2, gap="large")
    with left:
        section_heading("Open workload by department", "Use this to see where operator attention may be needed.")
        if open_rows:
            dept = pd.DataFrame(open_rows).groupby("department").size().reset_index(name="Open work orders").sort_values("Open work orders", ascending=False)
            st.bar_chart(dept.set_index("department"), horizontal=True, height=310)
        else: st.info("No open work orders.")
    with right:
        section_heading("Open cases by severity", "Priority tiers are heuristics, not service-level commitments.")
        sev_order = ["Critical", "High", "Medium", "Low"]
        sev_counts = pd.DataFrame([{"Severity": severity, "Count": sum(1 for item in open_rows if item.get("severity") == severity)} for severity in sev_order])
        st.bar_chart(sev_counts.set_index("Severity"), height=310)
    st.write("")
    lower_left, lower_right = st.columns([1, 1.15], gap="large")
    with lower_left:
        section_heading("Most reported issue types", "Counts reflect the current browser session only.")
        if rows:
            cat = pd.DataFrame(rows).groupby("category").size().reset_index(name="Reports").sort_values("Reports", ascending=False)
            st.dataframe(cat, hide_index=True, use_container_width=True, height=250)
    with lower_right:
        section_heading("Service area overview", "Explore the incident distribution on the interactive map.")
        render_map(rows, key="insights_map", height=310)
    st.download_button("Export all workspace data · CSV", data=all_frame.to_csv(index=False).encode("utf-8"), file_name="civicflow_all_incidents.csv", mime="text/csv", use_container_width=True)


st.markdown(
    '<div class="footer-note">CivicFlow · Code for Communities Chandigarh prototype. The default cases and sector-level map points are synthetic / illustrative. AI outputs and priority scores require human review. This workspace is not an official Chandigarh Administration or Municipal Corporation service and must not be used for emergency dispatch.</div>',
    unsafe_allow_html=True,
)
