"""Run every feature LIVE on the bundled sample data and record the responses
in cache/responses.json, so the app's demo mode replays real model output.

Usage:
    export OPENAI_API_KEY=sk-...      (Windows PowerShell:  $env:OPENAI_API_KEY="sk-...")
    python build_cache.py            # rebuilds everything (~70 small calls, well under $0.10 on gpt-4o-mini)
    python build_cache.py --only match   # rebuild one feature: profile | triage | chat | match | checkin
"""
import json
import sys

import features as F
import llm


def main():
    if not llm.has_key():
        sys.exit("Set OPENAI_API_KEY first (see README).")
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None

    # Drop old entries for the features being rebuilt (including any seed placeholders).
    cache = llm._load_cache()
    cache = {k: v for k, v in cache.items() if only and not k.startswith(only)}
    llm._save_cache(cache)

    listings = {p["id"]: p for p in F.load("listings")}

    if only in (None, "profile"):
        for p in sorted((F.DATA / "photos").iterdir()):
            if p.suffix.lower() in (".jpg", ".jpeg", ".png"):
                r = F.generate_profile(str(p), live=True)
                print(f"[B] {p.name}: status={r.get('photo_status')} review={r['human_review']}")
    if only in (None, "triage"):
        for m in F.load("inquiries"):
            r = F.triage(m, live=True)
            print(f"[C1] {m['id']}: {r['category']} / {r['urgency']} review={r['human_review']}")
    if only in (None, "chat"):
        for s in F.load("counselor_scripts"):
            r = F.counselor_turn(s["message"], listings[s["pet_id"]], s["persona"], True, f"chat:{s['id']}")
            print(f"[C2] {s['id']}: {r['outcome']}")
    if only in (None, "match"):
        for p in F.load("profiles"):
            r = F.match(p, listings[p["pet_id"]], live=True)
            print(f"[C3] {p['id']}: {r['rating']} votes={r['votes']}")
    if only in (None, "checkin"):
        for c in F.load("checkins"):
            r = F.checkin_radar(c, live=True)
            print(f"[D] {c['id']}: {r['risk_level']} (model said {r['model_risk_level']})")
    print(f"\nDone. {llm.cache_info()['count']} responses cached in {llm.CACHE_PATH}")


if __name__ == "__main__":
    main()
