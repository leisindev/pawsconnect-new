# PawsConnect AI Suite (MIS 552 - Homework 1)

A Streamlit demo of five AI features for a fictional pet-adoption platform:

| Tab | Part | Technique |
|---|---|---|
| 📸 Photo-to-Profile | B | Multi-modal vision (gpt-4o-mini), structured JSON, fallback prompting |
| 📥 Inquiry Triage | C1 | Few-shot classification (4 worked examples), fixed label set, JSON |
| 💬 Counselor Chat | C2 | Role-playing system prompt ("Juniper") + LLM-as-judge guardrail with regenerate / escalate |
| 🤝 Match Explainer | C3 | Chain-of-thought + self-consistency (3 runs at T=0.9, majority vote) |
| 📡 Check-in Radar | D | Chain-of-thought over a check-in time series + deterministic keyword safety net |

## Run it (no API key needed)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens in **Demo (cached)** mode and replays recorded model responses from `cache/responses.json`
for all bundled sample inputs. In each tab, pick a sample and press the button.

## Live mode

```bash
export OPENAI_API_KEY="sk-..."      # Windows PowerShell:  $env:OPENAI_API_KEY="sk-..."
streamlit run app.py
```

Select **Live (API)** in the sidebar. The key is read only from the environment; it is never stored in code.
Live mode also lets you upload your own photo, type your own inquiry, or edit the counselor message.

## Rebuilding the cache

```bash
python build_cache.py                # re-runs every feature on the sample data (well under $0.10)
python build_cache.py --only chat    # one feature: profile | triage | chat | match | checkin
```

## How the pieces fit

- `llm.py` - single entry point for every model call. Live mode calls OpenAI and records the reply under a
  cache key (`feature:input:step`); demo mode replays it. Because only this layer changes, the parsing,
  voting, judging and flagging logic in `features.py` runs identically in both modes.
- `prompts.py` - every final prompt. `prompts.md` documents them plus the iteration log
  (`python make_prompts_md.py` regenerates it).
- `features.py` - the pipelines. Code-level safety rules sit on top of the prompts:
  - B: `human_review` is forced true if any field is low confidence or the photo is not `ok`.
  - C1: a label outside the allowed set is forced to review.
  - C2: a judge verdict of "pass" with any failed rubric item is treated as "revise". On revise, the reply is
    regenerated once with the judge's feedback; if it fails again the user sees the human-escalation message.
  - C3: ties in the vote go to the more cautious rating; any disagreement sets the review flag.
  - D: the keyword safety net can only raise the risk level, never lower it; every result needs human review.
- `data/` - 3 pet listings, 10 inquiries (m08 and m09 are deliberately ambiguous), 3 adopter profiles,
  4 scripted counselor conversations (s3 and s4 use a deliberately weakened persona to show the judge
  catching bad drafts), 4 post-adoption check-in histories, and 5 photos (see `data/photos/LICENSES.md`).

## Sample photos

All bundled photos are CC0 (scikit-image sample data) or derived from CC0 images to create the hard cases:
blurry, low-light, two animals, and no animal.
