"""PawsConnect AI Suite - Streamlit demo.  Run:  streamlit run app.py"""
import html
from pathlib import Path

import streamlit as st

import features as F
import llm
import prompts as P

st.set_page_config(page_title="PawsConnect AI Suite", page_icon="🐾", layout="wide")

# ------------------------------------------------------------------ styling helpers
st.markdown("""
<style>
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:0.8rem;font-weight:600;margin:0 4px 4px 0;white-space:nowrap}
.b-red{background:#fde2e1;color:#9b1c1c}.b-orange{background:#feecdc;color:#9a3412}
.b-yellow{background:#fef9c3;color:#854d0e}.b-green{background:#dcfce7;color:#166534}
.b-blue{background:#dbeafe;color:#1e40af}.b-gray{background:#e5e7eb;color:#374151}
.card{border:1px solid rgba(128,128,128,.3);border-radius:12px;padding:16px 18px;margin-bottom:12px}
.muted{opacity:.7;font-size:.9rem}
table.tq{width:100%;border-collapse:collapse;font-size:.92rem}
table.tq th{text-align:left;border-bottom:2px solid rgba(128,128,128,.4);padding:6px}
table.tq td{border-bottom:1px solid rgba(128,128,128,.2);padding:6px;vertical-align:top}
</style>""", unsafe_allow_html=True)

COLORS = {"high": "green", "medium": "yellow", "low": "red",
          "critical": "red", "normal": "blue",
          "pass": "green", "revise": "red",
          "Strong Fit": "green", "Good Fit": "blue", "Possible Fit - needs a conversation": "yellow", "Poor Fit": "red",
          "settling_well": "green", "watch": "yellow", "call_this_week": "orange", "urgent_today": "red"}
URG_COLORS = {"critical": "red", "high": "orange", "normal": "blue", "low": "gray"}


def badge(text, color=None):
    c = color or COLORS.get(str(text), "gray")
    return f'<span class="badge b-{c}">{html.escape(str(text))}</span>'


def review_badge(flag):
    return badge("⚑ Needs human review", "orange") if flag else badge("✓ Auto-OK", "green")


def nice(label):
    return str(label).replace("_", " ").capitalize()


def run_safely(fn, *args):
    try:
        return fn(*args)
    except llm.CacheMiss as e:
        st.warning(f"No cached response for this input (`{e}`). Switch to **Live mode** to run it, "
                   "or run `python build_cache.py` with your API key.")
    except Exception as e:  # noqa: BLE001 - surface API errors in the UI
        st.error(f"Model call failed: {e}")
    return None


# ------------------------------------------------------------------ sidebar: mode
with st.sidebar:
    st.title("🐾 PawsConnect")
    st.caption("AI suite for a two-sided pet adoption platform")
    key_ok = llm.has_key()
    mode = st.radio("Mode", ["Demo (cached)", "Live (API)"], index=0,
                    help="Demo replays recorded model responses and needs no API key.")
    live = mode.startswith("Live")
    if live and not key_ok:
        st.error("OPENAI_API_KEY is not set in the environment. Falling back to demo mode.")
        live = False
    st.markdown(f"**Model:** `{llm.MODEL}`")
    info = llm.cache_info()
    st.markdown(f"**Cached responses:** {info['count']}")
    if info["sources"].get("seed"):
        st.warning(f"{info['sources']['seed']} cached responses are hand-written SEED placeholders for UI testing. "
                   "Run `python build_cache.py` with your key to replace them with real model output.")

listings = {p["id"]: p for p in F.load("listings")}

st.title("PawsConnect AI Suite")
st.caption(("🟢 LIVE: calling " + llm.MODEL) if live else "📼 DEMO MODE: replaying cached model responses (no API key needed)")

tabs = st.tabs(["🏠 Overview", "📸 Photo-to-Profile", "📥 Inquiry Triage", "💬 Counselor Chat",
                "🤝 Match Explainer", "📡 Check-in Radar (innovation)"])

# ------------------------------------------------------------------ Overview
with tabs[0]:
    st.subheader("What each tool does, and for whom")
    cols = st.columns(3)
    blurbs = [
        ("📸 Photo-to-Profile", "Shelter volunteers", "Upload one photo, get a draft adoption listing with confidence labels and a review flag."),
        ("📥 Inquiry Triage", "Shelter front desk", "Turns the inbox into a queue sorted by urgency, with the team to route each message to."),
        ("💬 Counselor Chat", "Adopters", "'Juniper' answers adoption questions. A second AI checks every reply before it is shown."),
        ("🤝 Match Explainer", "Adoption counselors", "Explains why a household and a pet fit (or don't), voted over 3 independent runs."),
        ("📡 Check-in Radar", "Post-adoption coordinator", "Reads adopters' check-ins over time and flags who to call this week to prevent returns."),
    ]
    for i, (t, who, d) in enumerate(blurbs):
        with cols[i % 3]:
            st.markdown(f'<div class="card"><b>{t}</b><br>{badge(who, "blue")}<br><span class="muted">{d}</span></div>',
                        unsafe_allow_html=True)
    st.info("Badges: ⚑ **Needs human review** means a person must check before acting. "
            "Nothing here posts, rejects, or contacts anyone automatically.")

# ------------------------------------------------------------------ Part B
with tabs[1]:
    st.subheader("Photo-to-Profile listing generator")
    st.caption("Vision model → structured listing. Fields the model cannot see are marked low confidence and flagged.")
    photos = sorted(p for p in (F.DATA / "photos").iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    c1, c2 = st.columns([1, 2])
    with c1:
        choice = st.selectbox("Sample photo", [p.name for p in photos])
        upload = st.file_uploader("…or upload your own (live mode)", type=["jpg", "jpeg", "png"])
        if upload is not None:
            tmp = F.ROOT / "cache" / f"upload_{upload.name}"
            tmp.write_bytes(upload.getvalue())
            photo_path = tmp
        else:
            photo_path = F.DATA / "photos" / choice
        st.image(str(photo_path), use_container_width=True)
        go = st.button("Generate listing", type="primary", key="gen_profile")
    with c2:
        if go or st.session_state.get("last_photo") == str(photo_path):
            st.session_state["last_photo"] = str(photo_path)
            prof = run_safely(F.generate_profile, str(photo_path), live)
            if prof:
                status = prof.get("photo_status", "ok")
                st.markdown(f'{review_badge(prof["human_review"])} {badge("Photo: " + nice(status), "green" if status == "ok" else "orange")}',
                            unsafe_allow_html=True)
                if status == "no_animal":
                    st.error(f"**No animal detected - no listing drafted.** {prof.get('photo_summary', '')}")
                    st.markdown(f"**Note for staff:** {prof.get('notes_for_staff', '')}")
                else:
                    if status != "ok":
                        st.warning(f"**Fallback applied:** {prof.get('photo_summary', '')}")
                    names = ", ".join(prof.get("suggested_names") or []) or "-"
                    rows = ""
                    for label, k in [("Species", "species"), ("Breed", "breed"), ("Estimated age", "age_range")]:
                        f = prof.get(k) or {}
                        rows += f"<tr><td><b>{label}</b></td><td>{html.escape(str(f.get('value', 'Unknown')))}</td><td>{badge(f.get('confidence', 'low'))}</td></tr>"
                    pers = prof.get("personality") or {}
                    care = "".join(f"<li>{html.escape(c)}</li>" for c in prof.get("care_requirements") or [])
                    st.markdown(f"""<div class="card">
                    <h3 style="margin-top:0">🐾 Suggested names: {html.escape(names)}</h3>
                    <table class="tq"><tr><th>Field</th><th>Draft</th><th>Confidence</th></tr>{rows}</table><br>
                    <b>About me</b> {badge(pers.get('confidence', 'low'))}<br>{html.escape(str(pers.get('value', '')))}<br><br>
                    <b>Care requirements</b><ul>{care}</ul>
                    <b>Adoption fee tier:</b> {badge(prof.get('fee_tier') or 'Not set', 'blue')}
                    <span class="muted">{html.escape(str(prof.get('fee_tier_reason', '')))}</span><br><br>
                    <b>⚠ Staff must check:</b> {html.escape(str(prof.get('notes_for_staff', '')))}
                    </div>""", unsafe_allow_html=True)
                    if prof["low_confidence_fields"]:
                        st.caption("Low-confidence fields: " + ", ".join(prof["low_confidence_fields"]))
                with st.expander("Developer view (raw model JSON)"):
                    st.json(prof)
    with st.expander("Fee tiers used by the model"):
        st.markdown("- **Sponsored** - seniors (8+) or visible special needs; fee waived or under $25\n"
                    "- **Standard** - healthy adult 1-7 years; $75\n- **Young** - under 1 year; $150 incl. first vaccines")

# ------------------------------------------------------------------ Part C1
with tabs[2]:
    st.subheader("Adoption inquiry triage queue")
    st.caption("Few-shot classifier with a fixed label set. Sorted most urgent first.")
    msgs = F.load("inquiries")
    custom = st.text_area("Add a message to triage (live mode)", "", height=70)
    if st.button("Run triage", type="primary") or st.session_state.get("triaged"):
        st.session_state["triaged"] = True
        batch = msgs + ([{"id": "custom_" + str(abs(hash(custom)) % 10**6), "text": custom}] if custom.strip() else [])
        rows = []
        for m in batch:
            r = run_safely(F.triage, m, live)
            if r:
                rows.append(r)
        rows.sort(key=lambda r: F.URGENCY_RANK[r["urgency"]])
        counts = {u: sum(r["urgency"] == u for r in rows) for u in P.URGENCY_LEVELS}
        st.markdown(" ".join(badge(f"{nice(u)}: {n}", URG_COLORS[u]) for u, n in counts.items())
                    + " " + badge(f"Needs review: {sum(r['human_review'] for r in rows)}", "orange"), unsafe_allow_html=True)
        body = ""
        for r in rows:
            sec = f"<br><span class='muted'>also: {nice(r['secondary_category'])}</span>" if r.get("secondary_category") else ""
            body += (f"<tr><td>{badge(nice(r['urgency']), URG_COLORS[r['urgency']])}</td>"
                     f"<td><b>{nice(r['category'])}</b>{sec}</td><td>{html.escape(r['suggested_routing'])}</td>"
                     f"<td>{html.escape(r['summary'])}<br><span class='muted'>Why: {html.escape(r['reason'])}</span></td>"
                     f"<td>{review_badge(r['human_review'])}</td></tr>")
        st.markdown(f"<table class='tq'><tr><th>Urgency</th><th>Category</th><th>Route to</th><th>Summary &amp; reason</th><th>Review</th></tr>{body}</table>",
                    unsafe_allow_html=True)
        with st.expander("Original messages"):
            for r in rows:
                st.markdown(f"**{r['id']}** - {r['message']}")
        with st.expander("Label definitions"):
            st.code(P.TRIAGE_PROMPT.split("EXAMPLES")[0], language="text")

# ------------------------------------------------------------------ Part C2
with tabs[3]:
    st.subheader("Chat with Juniper, the adoption counselor")
    st.caption("Every draft reply is reviewed by a second AI (the guardrail) before you see it.")
    scripts = F.load("counselor_scripts")
    pick = st.selectbox("Sample conversation", [f"{s['id']} · {s['label']}" for s in scripts])
    s = scripts[[f"{x['id']} · {x['label']}" for x in scripts].index(pick)]
    pet = listings[s["pet_id"]]
    st.markdown(f"Talking about **{pet['name']}** · persona: "
                + (badge("Weakened persona (test only)", "red") if s["persona"] == "weak" else badge("Production persona", "green")),
                unsafe_allow_html=True)
    if s["persona"] == "weak":
        st.caption("This test deliberately removes Juniper's honesty and scope rules so you can watch the guardrail catch a bad draft.")
    user_msg = st.text_area("Adopter message", s["message"], height=80, key=f"msg_{s['id']}")
    if st.button("Send", type="primary"):
        prefix = f"chat:{s['id']}" if user_msg == s["message"] else f"chat:custom:{abs(hash((user_msg, s['pet_id'], s['persona']))) % 10**8}"
        res = run_safely(F.counselor_turn, user_msg, pet, s["persona"], live, prefix)
        if res:
            st.session_state["chat_res"] = (s["id"], user_msg, res)
    if st.session_state.get("chat_res") and st.session_state["chat_res"][0] == s["id"]:
        _, umsg, res = st.session_state["chat_res"]
        with st.chat_message("user"):
            st.write(umsg)
        outcome_badge = {"passed": badge("Guardrail: PASS", "green"),
                         "revised": badge("Guardrail: REVISED, then passed", "orange"),
                         "escalated": badge("Guardrail: ESCALATED to a human", "red")}[res["outcome"]]
        with st.chat_message("assistant", avatar="🐾"):
            st.markdown(outcome_badge + (badge("Escalation tag", "red") if res["escalate_tag"] else ""), unsafe_allow_html=True)
            st.write(res["final"].replace("[ESCALATE]", "🚨").strip())
        with st.expander("What the guardrail saw (draft → verdict → revision)", expanded=res["outcome"] != "passed"):
            for step in res["trail"]:
                j = step["judge"]
                st.markdown(f"**{step['stage']}** {badge(j['verdict'].upper(), COLORS.get(j['verdict']))}", unsafe_allow_html=True)
                st.markdown(f"> {step['text']}")
                checks = " ".join(badge(("✓ " if ok else "✗ ") + nice(k), "green" if ok else "red") for k, ok in j.get("checks", {}).items())
                st.markdown(checks, unsafe_allow_html=True)
                st.caption("Judge feedback: " + j.get("feedback", ""))
                st.divider()

# ------------------------------------------------------------------ Part C3
with tabs[4]:
    st.subheader("Adopter-pet match explainer")
    st.caption("Chain-of-thought reasoning, sampled 3 times at temperature 0.9; the rating is a majority vote.")
    profs = F.load("profiles")
    pp = st.selectbox("Household", [f"{p['name']} → {listings[p['pet_id']]['name']}" for p in profs])
    prof = profs[[f"{p['name']} → {listings[p['pet_id']]['name']}" for p in profs].index(pp)]
    pet = listings[prof["pet_id"]]
    c1, c2 = st.columns(2)
    c1.markdown(f'<div class="card"><b>🏠 {prof["name"]}</b><br><span class="muted">{html.escape(prof["text"])}</span></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card"><b>🐾 {pet["name"]}</b> · {pet["breed"]}, {pet["age"]}<br><span class="muted">{html.escape(pet["temperament"])}<br>Good with: {html.escape(pet["good_with"])}</span></div>', unsafe_allow_html=True)
    if st.button("Explain the fit", type="primary"):
        st.session_state["match_for"] = prof["id"]
    if st.session_state.get("match_for") == prof["id"]:
        m = run_safely(F.match, prof, pet, live)
        if m:
            agree = m["votes"][m["rating"]]
            st.markdown(f"### {badge(m['rating'])} {review_badge(m['human_review'])}", unsafe_allow_html=True)
            st.markdown(f"**{agree} of {m['n']} runs** rated this **{m['rating']}**"
                        + ("" if m["unanimous"] else " - the runs disagreed, so a counselor should review."))
            st.markdown(" ".join(badge(f"Run {i + 1}: {r['rating']}") for i, r in enumerate(m["runs"])), unsafe_allow_html=True)
            w = m["winner"]
            reasons = "".join(f"<li>{html.escape(x)}</li>" for x in w.get("top_reasons", []))
            st.markdown(f'<div class="card"><b>Top reasons</b><ol>{reasons}</ol><b>⚠ Top concern:</b> {html.escape(w.get("top_concern", ""))}</div>',
                        unsafe_allow_html=True)
            with st.expander("Show step-by-step reasoning (winning run)"):
                for step in w.get("reasoning_steps", []):
                    st.markdown(f"- {step}")
            with st.expander("Compare all runs"):
                for i, r in enumerate(m["runs"]):
                    st.markdown(f"**Run {i + 1}: {r['rating']}** - concern: {r.get('top_concern', '')}")

# ------------------------------------------------------------------ Part D
with tabs[5]:
    st.subheader("📡 Post-Adoption Check-in Radar")
    st.caption("For the post-adoption coordinator: who should I call this week to prevent a return? "
               "Chain-of-thought over the whole check-in history + a keyword safety net that can only raise risk, never lower it.")
    cases = F.load("checkins")
    if st.button("Scan all active adoptions", type="primary") or st.session_state.get("radar"):
        st.session_state["radar"] = True
        results = [r for r in (run_safely(F.checkin_radar, c, live) for c in cases) if r]
        results.sort(key=lambda r: -F.RISK_RANK[r["risk_level"]])
        st.markdown(" ".join(badge(f"{nice(l)}: {sum(r['risk_level'] == l for r in results)}", COLORS[l]) for l in reversed(P.RISK_LEVELS)),
                    unsafe_allow_html=True)
        for r in results:
            with st.container(border=True):
                a, b = st.columns([3, 1])
                a.markdown(f"**{r['adopter']}** · {r['pet']}")
                a.markdown(badge(nice(r["risk_level"]), COLORS[r["risk_level"]]) + badge("Trend: " + r.get("trajectory", "?"),
                           {"improving": "green", "stable": "blue", "worsening": "red"}.get(r.get("trajectory"), "gray"))
                           + (badge(f"Safety net raised from '{nice(r['model_risk_level'])}'", "orange") if r["overridden"] else ""),
                           unsafe_allow_html=True)
                b.markdown(" ".join(
                    {"positive": "🟢", "mixed": "🟡", "negative": "🔴"}.get(x.get("mood"), "⚪") + " " + x.get("when", "")
                    for x in r.get("mood_by_checkin", [])))
                st.markdown(f"**Suggested action:** {r.get('suggested_action', '')}")
                if r.get("risk_signals"):
                    st.caption("Signals: " + " · ".join(f"“{s}”" for s in r["risk_signals"]))
                with st.expander("Reasoning and draft outreach"):
                    for step in r.get("reasoning", []):
                        st.markdown(f"- {step}")
                    st.text_area("Draft message (edit before sending - never sent automatically)",
                                 r.get("draft_outreach", ""), key=f"draft_{r['id']}")
