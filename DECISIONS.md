# Decisions

This is a product and technical decision log — closer to a lightweight PRD than a rules file. It documents what was built, why, and what was deliberately left out. It is written for humans: engineers reading the code, collaborators onboarding to the project, or the author revisiting a choice months later.

**Agents do not read this file.** Rules, limits, and alert logic live in the Python package and the family's profile. This document explains the reasoning behind those choices — it does not drive any runtime behavior.

---

## Primary decisions 

### 1. Deterministic code does the math; the LLM operates the system

**Context.** The first version asked the agent to read the log, count, and draw charts on every run.

**Decision.** Move every count, threshold and chart into a tested Python package. The agent fetches data, runs the package, adds one sentence of summary, and delivers.

**Why.** A report shown to a doctor must be correct and identical for identical input. Model-written counting was usually right; charts drifted between runs.

**Trade-off.** Less flexibility: a new metric now needs code and a test instead of a prompt edit.

### 2. Preset areas and medications - simplicity in day to day logging

**Context.** The log is filled in during bedtime with a toddler in one arm. When a parent needs to input data, they need to be quick but precise.

**Decision.** A small set of large buttons (default: five) determined by the questionnaire and tailored to each parent. Dates are pre-selected to the current date and time; most entries take two to three taps to record.

**Why.** Every extra field is an entry that doesn't get logged. Time of day added nothing for these treatments.

**Trade-off.** Without detailed context, smaller areas are grouped under a larger umbrella (ex: Wrists under Arms), which can lead to additional triggers if the parent applies a cream to a smaller area but the full body part is counted for tracking. Simplicity takes priority. If a specific area needs separate attention (ex: Diaper, Neck) it can be added during the questionnaire.

### 3. Body areas are named categories, not free text

**Context.** Free-text areas ("shoulders", "small side", etc.) made counts impossible to compare — the same body part logged differently across days can't be aggregated. Free text also increases input time, which at bedtime means entries that don't get logged.

**Decision.** The questionnaire asks the parent to define their own area list. The default is seven categories: Arms, Legs, Stomach, Back, Neck, Face, Diaper. Sub-areas roll up to a parent category via aliases (shoulders → Arms, ankles → Legs). No automatic left/right split — if a family needs that granularity, they define "Left arm" and "Right arm" as separate areas.

**Why.** Named categories keep per-area counts meaningful and comparable week to week, without locking every family into one anatomy.

**Trade-off.** Areas must be decided at setup; renaming one later would break historical counts, as entries store the area name as logged and are matched against the current profile at read time.

**Risk accepted.** Accepted risk for MVP. A good post-MVP improvement would be to support free-text aliases and backfill category changes across historical data.

### 4. "Full body" is defined by the family, not hardcoded

**Context.** Parents often apply a cream to the whole body in one go, and logging each area separately at that moment is impractical. At the same time, not every area should be treated as interchangeable — sensitive areas like face and diaper have different products and tighter limits.

**Decision.** The questionnaire asks which of the family's tracked areas "full body" covers. The default suggestion is every area except those in the sensitive-skin set (face, diaper, scalp). A full-body log entry counts once for each area it covers; the rest are always tracked separately.

**Why.** Face and diaper skin are typically treated with different products and limits — folding them into "full body" would hide overuse. But which areas make up "full body" differs by family, so it belongs in the profile, not the code.

**Trade-off.** A family that skips defining "full body" or sets it up incorrectly may unintentionally under-count applications — logging "full body" when only some areas were treated, or missing sensitive areas that should have been tracked separately. The questionnaire mitigates this, but the correctness of the counts depends on the setup being accurate.

**Risk accepted.** Accepted for MVP. Two post-MVP improvements worth prioritising: (1) a guided confirmation step at the end of the questionnaire that shows exactly which areas "full body" will count toward, so misconfig is caught before any data is logged; (2) a backfill tool that allows a parent to correct their full body definition and re-expand historical entries against the updated profile.

### 5. Weekly steroid load = average applications per *treated* area

**Context.** A parent wants to know if they're over-treating a specific area — not just how many times the steroid was used in total. Counting total days misses the point: a week where steroid went on Legs twice and Arms once scores "3", even though neither area was hit more than twice. That number doesn't reflect what actually happened to any one patch of skin.

**Decision.** Sum the per-area counts and divide by the number of areas treated that week (Legs 2 + Arms 1 → 1.5).

**Why.** Answers the real question: how hard is each affected area being hit? Dividing by all tracked areas would let untreated areas dilute a genuinely heavy week.

**Trade-off.** An average can hide a single hot spot — one area used 4 times can sit behind a low average if others were mild. That's why the per-area alert stays alongside the average: the average tells the story of the week, the per-area alert catches the outlier.

## Smaller decisions 

### 6. Silent by default

**Decision.** The nightly agent sends nothing on a quiet night. Alerts are bundled into one push that starts with the most important item.
**Why.** An alert every night is an alert nobody reads.

### 7. Small multiples instead of one crowded chart

**Context.** Seven area lines on one chart crossed constantly and couldn't be labelled.
**Decision.** One mini chart per area on a shared scale, with each area's 12-week average as a grey dashed line and a rising/falling tag.
**Why.** You can read each area at a glance and still compare heights.

### 8. Rolling 12-week average, not "since the start"

**Decision.** The grey baseline is the last 12 weeks; if the log is younger, it averages over the weeks logged.
**Why.** "Since the start" gets slower to reflect change every month. Twelve weeks means "her normal lately".

### 9. Real data never enters the repo

**Decision.** Publish the production code with synthetic data. Real entries, profile and links live in a git-ignored `private/` folder and in the hosted log. A test scans published files for emails, private links and a local denylist.
**Why.** One codebase for the portfolio and for real use, with no way to leak a child's health data by accident.

### 10. Treatments are data, set up by a questionnaire

**Context.** The first version hard-coded one family's three treatments.
**Decision.** A profile lists the family's creams (name, where used, schedule, limits), their antihistamine brand and limit, and whether to track allergens. A first-use questionnaire writes it; a validator checks it; the page, alerts and report are generated from it.
**Why.** Every family's treatment plan is different, and the code shouldn't change when a cream does.
**Trade-off.** Scope stays deliberately narrow: topical creams, one antihistamine, flares, allergen exposure. Oral steroids, injections, and dosing schedules are out.

**Post-MVP.** Expanding to other medication types — oral steroids, biologics, dosing schedules — is the natural next step as the profile system is already built to be data-driven. Each would need its own tracking model (doses, not days; weight-based limits, etc.) and is scoped out until the core use case is validated.

### 11. Allergen exposure: one tap for the common nine

**Decision.** If tracked, the page shows buttons for the 9 major allergens plus "Other", with a free-text amount. Exposures appear in the weekly report and as context on nightly alerts; they never trigger an alert on their own.
**Why.** Introductions are planned and logged in a hurry; buttons beat typing. Showing exposures next to flares lets the parent and doctor judge timing.

### 12. Old entries keep working

**Decision.** A cream's id is its entry type, so entries logged before profiles existed ("steroid", "taci") are already valid. Missing fields (no slot, no time) are treated as "once that day".
**Why.** Months of history shouldn't need a migration to survive a model change.
