"""Feature pipelines. Each function runs identically in live and demo mode;
only llm.chat() decides whether the text comes from the API or the cache."""
import json
from collections import Counter
from pathlib import Path

import llm
import prompts as P

ROOT = Path(__file__).parent
DATA = ROOT / "data"


def load(name):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def listing_text(pet: dict) -> str:
    skip = {"id"}
    return "\n".join(f"- {k.replace('_', ' ').title()}: {v}" for k, v in pet.items() if k not in skip)


# ---------------------------------------------------------------- Part B
def generate_profile(photo_path: str, live: bool) -> dict:
    key = f"profile:{Path(photo_path).name}"
    messages = [{"role": "user", "content": [
        {"type": "text", "text": P.PROFILE_PROMPT},
        llm.image_part(photo_path),
    ]}]
    out = llm.parse_json(llm.chat(messages, key, live, temperature=0.2))

    # Belt and braces: enforce the human_review rule in code, not only in the prompt.
    low_fields = [f for f in ("species", "breed", "age_range", "personality")
                  if isinstance(out.get(f), dict) and out[f].get("confidence") == "low"]
    out["low_confidence_fields"] = low_fields
    out["human_review"] = bool(out.get("human_review")) or bool(low_fields) or out.get("photo_status") != "ok"
    return out


# ---------------------------------------------------------------- Part C1
URGENCY_RANK = {u: i for i, u in enumerate(P.URGENCY_LEVELS)}


def triage(msg: dict, live: bool) -> dict:
    prompt = P.TRIAGE_PROMPT.replace("{message}", msg["text"])
    out = llm.parse_json(llm.chat([{"role": "user", "content": prompt}],
                                  f"triage:{msg['id']}", live, temperature=0))
    # Guard the label set: anything outside it is forced to review.
    if out.get("category") not in P.TRIAGE_LABELS:
        out["category"], out["human_review"] = "spam_or_other", True
        out["reason"] = f"(label outside allowed set) {out.get('reason', '')}"
    if out.get("urgency") not in URGENCY_RANK:
        out["urgency"], out["human_review"] = "high", True
    out["id"], out["message"] = msg["id"], msg["text"]
    return out


def triage_all(msgs, live):
    rows = [triage(m, live) for m in msgs]
    return sorted(rows, key=lambda r: URGENCY_RANK[r["urgency"]])


# ---------------------------------------------------------------- Part C2
def counselor_turn(user_message: str, pet: dict, persona: str, live: bool, key_prefix: str) -> dict:
    """Draft -> judge -> (if revise) regenerate once with feedback -> judge again -> else escalate."""
    listing = listing_text(pet)
    system = (P.WEAK_PERSONA_PROMPT if persona == "weak" else P.PERSONA_PROMPT).format(listing=listing)
    convo = [{"role": "system", "content": system}, {"role": "user", "content": user_message}]

    draft = llm.chat(convo, f"{key_prefix}:draft", live, temperature=0.7, json_mode=False)
    verdict = _judge(listing, user_message, draft, live, f"{key_prefix}:judge1")
    trail = [{"stage": "Draft reply", "text": draft, "judge": verdict}]

    if verdict["verdict"] == "revise":
        # The revision always uses the full-strength persona plus the judge's feedback.
        strong = P.PERSONA_PROMPT.format(listing=listing)
        retry = [{"role": "system", "content": strong}, {"role": "user", "content": user_message},
                 {"role": "assistant", "content": draft},
                 {"role": "user", "content": P.REVISION_INSTRUCTION.format(feedback=verdict["feedback"])}]
        revised = llm.chat(retry, f"{key_prefix}:revised", live, temperature=0.3, json_mode=False)
        verdict2 = _judge(listing, user_message, revised, live, f"{key_prefix}:judge2")
        trail.append({"stage": "Regenerated with judge feedback", "text": revised, "judge": verdict2})
        if verdict2["verdict"] == "pass":
            final, outcome = revised, "revised"
        else:
            final, outcome = P.ESCALATION_MESSAGE, "escalated"
    else:
        final, outcome = draft, "passed"
    return {"final": final, "outcome": outcome, "trail": trail,
            "escalate_tag": final.strip().startswith("[ESCALATE]")}


def _judge(listing, user_message, draft, live, key):
    prompt = P.JUDGE_PROMPT.format(listing=listing, user_message=user_message, draft=draft)
    out = llm.parse_json(llm.chat([{"role": "user", "content": prompt}], key, live, temperature=0))
    # A verdict that claims pass while any check failed is treated as revise.
    if out.get("verdict") == "pass" and not all(out.get("checks", {}).values()):
        out["verdict"] = "revise"
    return out


# ---------------------------------------------------------------- Part C3
def match(profile: dict, pet: dict, live: bool, n_runs: int = 3) -> dict:
    prompt = P.MATCH_PROMPT.format(profile=profile["text"], listing=listing_text(pet))
    runs = []
    for i in range(n_runs):
        txt = llm.chat([{"role": "user", "content": prompt}], f"match:{profile['id']}:{pet['id']}:run{i}",
                       live, temperature=0.9, max_tokens=1100)
        r = llm.parse_json(txt)
        if r.get("rating") not in P.FIT_SCALE:  # map near-miss labels onto the scale
            r["rating"] = next((s for s in P.FIT_SCALE if s.split(" -")[0].lower() in str(r.get("rating")).lower()),
                               "Possible Fit - needs a conversation")
        runs.append(r)
    votes = Counter(r["rating"] for r in runs)
    top, top_n = votes.most_common(1)[0]
    if list(votes.values()).count(top_n) > 1:  # tie -> take the more cautious label
        top = max((s for s, c in votes.items() if c == top_n), key=P.FIT_SCALE.index)
    winner = next(r for r in runs if r["rating"] == top)
    return {"rating": top, "votes": dict(votes), "n": n_runs, "unanimous": len(votes) == 1,
            "winner": winner, "runs": runs, "human_review": len(votes) > 1 or top.startswith(("Possible", "Poor"))}


# ---------------------------------------------------------------- Part D
RISK_RANK = {r: i for i, r in enumerate(P.RISK_LEVELS)}
SAFETY_TERMS = {  # deterministic floor: these words can never be scored as "settling well"
    # v1 used the bare word "bite", which flagged normal kitten play-biting ("bites our hands")
    # as urgent. v2 matches bite *incidents* only. See prompts.md, Part D iteration.
    "urgent_today": ["broke the skin", "snapped at", "bit my", "bit our", "bit him", "bit her", "bit a ",
                     "blood", "not eating for", "in the garage", "locked in", "kept outside"],
    "call_this_week": ["return", "rehome", "give him up", "give her up", "can't keep", "or he goes",
                       "or she goes", "landlord", "out of ideas"],
}


def checkin_radar(case: dict, live: bool) -> dict:
    text = "\n".join(f"[{c['when']}] {c['text']}" for c in case["checkins"])
    prompt = P.CHECKIN_PROMPT.format(pet=case["pet"], checkins=text)
    out = llm.parse_json(llm.chat([{"role": "user", "content": prompt}], f"checkin:{case['id']}",
                                  live, temperature=0, max_tokens=1100))
    model_level = out.get("risk_level") if out.get("risk_level") in RISK_RANK else "call_this_week"
    lowered = text.lower()
    floor, hits = "settling_well", []
    for level, terms in SAFETY_TERMS.items():
        for t in terms:
            if t in lowered:
                hits.append(t.strip())
                if RISK_RANK[level] > RISK_RANK[floor]:
                    floor = level
    final = max(model_level, floor, key=RISK_RANK.get)
    out.update({"model_risk_level": model_level, "risk_level": final, "keyword_hits": hits,
                "overridden": final != model_level, "human_review": True,
                "adopter": case["adopter"], "pet": case["pet"], "id": case["id"]})
    return out
