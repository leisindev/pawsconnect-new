Each entry: version 1, the problem observed, version 2, and what changed.

## Iteration 1 - Part D safety net: "bite" over-triggered (observed while building)

**v1.** The keyword safety net that can raise (never lower) the model's risk level included the bare term `bite`
in the `urgent_today` list.

**Problem observed.** The Patel household's week-2 check-in says Luna the kitten "still bites our hands
sometimes but we're using toys like you said". The model correctly rated the adoption `settling_well`, but the
safety net matched `bite` and raised it to **urgent today**. A coordinator would have made an alarming phone
call to a happy family about normal kitten play.

**v2.** Replaced the bare word with phrases that describe a bite *incident*: `broke the skin`, `snapped at`,
`bit my`, `bit our`, `bit him`, `bit her`, plus confinement signals (`in the garage`, `locked in`, `kept outside`).

**What changed.** Patel now stays `settling_well`; Garcia (a bite that "broke the skin" on a 5-year-old, dog
moved to the garage) is still raised from the model's `call_this_week` to `urgent_today`.
Lesson: a deterministic rule is only as safe as its vocabulary. Keyword lists trade false alarms against misses,
which is why the model's reasoning and the human review flag stay in the loop.

## Iteration 2 - [YOUR LIVE-MODE ITERATION GOES HERE]

<!-- Run one of the v1 prompts below in live mode, note what went wrong, then compare with the final prompt.
     Paste the real outputs. Delete this comment block when done. -->

**v1.** (suggested test: Photo-to-Profile without fallback rules 1-4)

```text
You are the listing assistant for PawsConnect. Look at this pet photo and write an adoption profile as JSON with:
suggested_names, species, breed, age_range, personality, care_requirements, fee_tier, human_review.
```

**Problem observed.** _(e.g. on 02_hard_blurry.jpg did it name a specific breed with confidence? On
05_hard_no_animal.jpg did it invent a pet? Paste the output.)_

**v2.** The final `PROFILE_PROMPT` (Part 2 below): confidence label definitions, the `photo_status` fallback
ladder, the explicit "Mixed / unknown breed" rule, and "personality cannot be seen in a photo".

**What changed.** _(your observation of the same photo with v2)_

### Other v1 candidates worth testing if you want a second iteration
- **Triage, zero-shot:** the final TRIAGE_PROMPT with the EXAMPLES block deleted. Check whether m08/m09 (the
  ambiguous messages) get `human_review: true` and a `secondary_category` without the examples.
- **Judge, no rubric:** "Is this reply OK to send? Answer pass or revise." Run it on chat s4 and see whether it
  notices that Duke's listing says "must be only dog".
