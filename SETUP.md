# First-use setup (for Claude)

Run this when `private/profile.json` does not exist, or when the parent asks to redo setup.
It builds the family's profile by conversation. The terminal version, `python -m patchwork init`,
asks the same questions; both write the same file.

## How to run it

- Ask **one topic at a time**, in plain language, and wait for the answer. Offer the default in brackets.
- Reflect back what you heard before moving on when an answer is ambiguous.
- Never suggest a medication, dose or limit. All limits come from the parent's doctor.
- Keep everything you hear in `private/`. Nothing from setup goes into a tracked file.

## Limits

Limits are handled as a dedicated step within each relevant section (creams, antihistamine). Before asking any limit question, say:

> "Limits are alert thresholds from your doctor's instructions — Patchwork will notify you when one is crossed. They are completely optional: if you don't set a limit, Patchwork won't alert for that item since it has nothing to compare against. You can always add or update a limit later."

Then ask the limit question(s) for that item. If the parent skips (blank answer), record `null` — no alert will fire.

## The questions

**1. Body areas**
- "Which body areas do you track?" Default: Arms, Legs, Stomach, Back, Neck, Face, Diaper.
- Follow-ups to get the scope right:
  - "Do you need left and right separately?" If yes, list each side as its own area ("Left arm", "Right arm").
  - "Smaller spots like elbows, knees, ankles are automatically grouped under Arms or Legs. Do you want any of them tracked separately as their own area?" Reflect back the final list simply, e.g. "So: Arms, Legs, Hands." Spots the parent wants separate become their own tracked area; for the rest, record aliases that group each sub-spot under its closest tracked parent (e.g. if Hands is tracked, fingers/thumbs/wrists go under Hands; if only Arms is tracked, they go under Arms).
  - If an area seems very broad (e.g. "Body") or very narrow (e.g. "Left thumb"), ask whether that's the level they want to count at.

**2. Full body**
- "When you log 'full body', which of your areas does that cover?" Suggest every area except face, diaper and scalp. Confirm the areas that stay separate.

**3. Creams** — repeat for each cream (up to 6)
- "What's the cream called?"
- "Do you apply this ointment to a specific area, or anywhere it's needed?" (e.g. face only → Face)
- "Do you apply this at a fixed time each day, or do you need to track morning and night separately?" If they track both times: log as Morning / Night. If once a day at a consistent time: log by date. Either way, it counts as at most once a day.
- "Is there anything you apply regularly that you don't want tracked in Patchwork?" Note it in `private/helper.md`, not the profile.
- **Limits** (say the limits preamble, then ask):
  - If used on more than one area: "How many days in a week on one area before I alert you?" (blank = no alert)
  - "How many days in a week total before I alert you?" (blank = no alert)

**4. Medications**
- "Any medications to track — antihistamine, montelukast, or anything else?" First one defaults to Antihistamine. Up to 4.
- For each: "What's it called?" then the limits preamble, then:
  - "Alert when it's given more than N times within a window? N = " and "...within how many days?" (blank = no alert for either)
- When done: Enter with no name to move on.

**5. Allergen exposure**
- "Do you want to log allergen exposure — food introductions or accidental contact?"
- If yes: the page shows buttons for the 9 major allergens (Milk, Egg, Fish, Shellfish, Tree nuts, Peanut, Wheat, Soy, Sesame) plus "Other". Ask: "Any others you'd like a button for?" Each exposure is logged with date and time, the allergen and the amount.

**6. Delivery**
- Email for the weekly report, timezone, report day and time.

**7. History (optional)**
- "Do you have past entries to bring in?" Accept pasted text; convert each line to an entry and confirm the count before saving to `private/entries-export.json`.

## Then

1. Read the summary back, grouped as above, and ask "Save this?"
2. Write `private/profile.json` in the shape of `rules.json`. Cream ids are lowercase slugs of the name and can't be `anti`, `flare`, `allergen` or `note`.
3. Run `python -m patchwork validate` and fix anything it reports.
4. If the family uses the hosted log page, also save the profile as the log's `config/profile` document. The page and the scheduled agents read it from there, so it is the one live copy; `private/profile.json` is the local copy for running reports on the laptop.
5. Otherwise run `python -m patchwork page` to build `private/dist/index.html` with the profile baked in.
6. Run `pytest -q` to confirm nothing personal leaked into tracked files.
