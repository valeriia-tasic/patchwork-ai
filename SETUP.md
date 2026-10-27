# First-use setup (for Claude)

Run this when `private/profile.json` does not exist, or when the parent asks to redo setup.
It builds the family's profile by conversation. The terminal version, `python -m patchwork init`,
asks the same questions; both write the same file.

## How to run it

- Ask **one topic at a time**, in plain language, and wait for the answer. Offer the default in brackets.
- Reflect back what you heard before moving on when an answer is ambiguous.
- Never suggest a medication, dose or limit. Limits are the parent's own alert thresholds from their doctor. Say this once, before the first limit question:
  > "Limits are alert thresholds you set from your doctor's instructions. Patchwork doesn't recommend limits; it only tells you when one is crossed."
- Keep everything you hear in `private/`. Nothing from setup goes into a tracked file.

## The questions

**1. Body areas**
- "Which body areas do you track?" Default: Arms, Legs, Stomach, Back, Neck, Face, Diaper.
- Follow-ups to get the scope right:
  - "Do you need left and right separately?" If yes, list each side as its own area ("Left arm", "Right arm").
  - "Is there anything you'd log that belongs under one of these — elbows, ankles, shoulders?" Record each as an alias (`"elbows": "Arms"`).
  - If an area seems very broad (e.g. "Body") or very narrow (e.g. "Left thumb"), ask whether that's the level they want to count at.

**2. Full body**
- "When you log 'full body', which of your areas does that cover?" Suggest every area except face, diaper, scalp and groin. Confirm the areas that stay separate.

**3. Creams** — repeat for each cream (up to 6)
- "What's the cream called?"
- "Is it used on any area, or only on some?" (e.g. a face cream → Face only)
- "Do you log it once a day by date, or as Morning / Night?" Every cream is at most once a day; Morning / Night records *when*, it doesn't double the count.
- If used on more than one area: "Should I alert you when one area gets it on more than N days in a week? What's N?" (blank = no alert)
- "Should I alert you when it's used on more than N days a week in total?" (blank = no alert)
- "Is there routine use you *don't* want logged — e.g. a daily body moisturiser?" Note it in `private/helper.md`, not the profile.

**4. Antihistamine**
- "Do you give an antihistamine? What brand?" (e.g. Zyrtec, Claritin)
- "Alert me when it's given more than how many times within how many days?" Default 1 in 3.

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
