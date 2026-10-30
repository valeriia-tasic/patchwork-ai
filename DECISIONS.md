# Decisions

Short records of product and technical choices: what we decided, why, and what we gave up.

---

### 1. Deterministic code does the math; the LLM operates the system

**Context.** The first version asked the agent to read the log, count, and draw charts on every run.
**Decision.** Move every count, threshold and chart into a tested Python package. The agent fetches data, runs the package, adds one sentence of summary, and delivers.
**Why.** A report shown to a doctor must be correct and identical for identical input. Model-written counting was usually right; charts drifted between runs.
**Trade-off.** Less flexibility: a new metric now needs code and a test instead of a prompt edit.

### 2. One tap, two at most

**Context.** The log is filled in during bedtime with a toddler in one arm.
**Decision.** Five big buttons. Steroid and face cream are date-only (today by default); the face cream button preselects its only area.
**Why.** Every extra field is an entry that doesn't get logged. Time of day added nothing for these treatments.
**Trade-off.** No time-of-day analysis for creams.

### 3. Body areas are seven fixed categories

**Context.** Free-text areas ("shoulders", "small side", "dots on thumbs") made counts impossible to compare.
**Decision.** Seven categories: Arms, Legs, Stomach, Back, Neck, Face, Diaper. Sub-areas roll up (shoulders → Arms, ankles → Legs, side → Back).
**Why.** Matches how the parent and the doctor talk about it, and keeps per-area counts meaningful.
**Trade-off.** Can't see whether one arm is worse than the other.

### 4. "Full body" means arms, legs, stomach, back and neck

**Decision.** A full-body application counts once for each of those five areas. Face and diaper area are always logged separately.
**Why.** Face and diaper skin are treated with different products and limits, so folding them into "full body" would hide them.

### 5. Weekly steroid load = average applications per *treated* area

**Context.** Counting "days steroid was used" called a week with Legs ×2 and Arms ×1 a "3", even though no area got more than 2.
**Decision.** Sum the per-area counts and divide by the number of areas treated that week (Legs 2 + Arms 1 → 1.5).
**Why.** Answers the real question, "how hard is each affected area being hit?" Dividing by all seven areas would let untreated areas dilute a bad week.
**Trade-off.** An average can hide a single hot spot. That's why the per-area "more than 2 in a week" alert stays, next to the average.

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
**Trade-off.** Scope stays deliberately narrow: topical creams, one antihistamine, flares, allergen exposure. Oral steroids, injections and dosing schedules are out.

### 11. Creams are once a day; Morning / Night records when, not how many

**Decision.** Each cream is set to date-only or Morning / Night. Limits count days, so a morning and a night entry on the same area and day count once.
**Why.** The creams this was built around are applied at most once a day; the slot answers "when", which matters for some creams, without inflating counts.
**Trade-off.** A twice-daily cream would need application counting; not supported.

### 12. Allergen exposure: one tap for the common nine

**Decision.** If tracked, the page shows buttons for the 9 major allergens plus "Other", with a free-text amount. Exposures appear in the weekly report and as context on nightly alerts; they never trigger an alert on their own.
**Why.** Introductions are planned and logged in a hurry; buttons beat typing. Showing exposures next to flares lets the parent and doctor judge timing.

### 13. Old entries keep working

**Decision.** A cream's id is its entry type, so entries logged before profiles existed ("steroid", "taci") are already valid. Missing fields (no slot, no time) are treated as "once that day".
**Why.** Months of history shouldn't need a migration to survive a model change.
