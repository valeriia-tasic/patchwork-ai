# Getting started

From zero to a one-tap log page on your phone in about 15 minutes.

---

## What you need

| You need | Why |
|---|---|
| A **Claude Pro, Max, Team or Enterprise** account | Runs the setup, publishes the log page, and runs the scheduled agents |
| **Claude Code** installed | Runs the setup questionnaire inside this repo |
| **Python 3.10+** and **git** | Installs the patchwork package that does all the counting |

---

## 1. Install Claude Code

```bash
curl -fsSL https://claude.ai/install.sh | bash
claude --version
```

The first time you run `claude` it opens your browser to sign in. Full instructions: [Claude Code setup](https://code.claude.com/docs/en/setup).

## 2. Clone and install

```bash
git clone https://github.com/valeriia-tasic/patchwork-ai.git
cd patchwork-ai

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Set up your profile

```bash
claude
```

Because there's no profile yet, Claude starts the setup questionnaire automatically. If it doesn't, type **"run setup"**. It asks one topic at a time:

1. Body areas you track
2. What "full body" covers
3. Each cream: name, areas, schedule, and optional alert limits
4. Medications (antihistamine, etc.) and optional alert limits
5. Whether to log allergen exposure
6. Email, timezone, report day

Limits are optional and come from **your doctor's instructions**. Leave any blank and nothing alerts for it.

## 4. Publish the log page

After setup, Claude builds `private/dist/index.html`. Now publish it so you can open it on your phone:

1. Open [claude.ai](https://claude.ai) in your browser (the regular chat, not Claude Code).
2. Send this message:

   > "Publish this as an artifact with a database enabled:"

   Then paste the full contents of `private/dist/index.html`.

3. Claude creates the artifact and gives you a URL like `https://claude.ai/artifact/…`

4. In the same chat, save your profile to the database so the page stays up to date if you change settings later:

   > "Save my profile as the `config/profile` document in this artifact's database:"

   Then paste `private/profile.json`.

## 5. Add to your phone's home screen

Open the artifact URL in your phone's browser:

- **iPhone (Safari):** tap the Share icon → "Add to Home Screen" → Add
- **Android (Chrome):** tap the three-dot menu → "Add to Home Screen" → Add

The page appears on your home screen like a native app. Tap it to open the log directly.

## 6. Log entries

**From the page:** tap a button (Steroid, Taci, Zyrtec, Flare, Note), fill in details, tap Save. Done.

**By conversation:** tell Claude what happened — "steroid on arms today", "gave Zyrtec at 7pm", "flare on her neck after swimming" — and it logs it to the database.

## 7. Reports and alerts

Ask Claude in conversation:

> "Run this week's report"
> "Any alerts tonight?"

Claude runs the analysis and explains the numbers. It never counts by hand.

## 8. Set up nightly alerts and the weekly report

To get these automatically — no laptop needed — create two scheduled tasks in claude.ai.

The prompts are in `prompts/nightly.md` and `prompts/weekly.md`. Each needs four values:

| Placeholder | What to put |
|---|---|
| `{{REPO_URL}}` | Your fork's git URL |
| `{{LOG_URL}}` | The artifact URL from step 4 |
| `{{TZ}}` | Your timezone, e.g. `America/New_York` |
| `{{EMAIL}}` | Your email (weekly prompt only) |

In claude.ai, tell Claude:

> "Create a scheduled task that runs every day at 8pm using this prompt:" (paste `prompts/nightly.md` with placeholders filled in)

> "Create a scheduled task that runs every Sunday at 8pm using this prompt:" (paste `prompts/weekly.md` with placeholders filled in)

---

## Before you push anything

If you fork this repo and commit changes, run `pytest -q` first. `tests/test_privacy.py` fails the build if an email address, a private link, or any term from your own `private/denylist.txt` appears in a file git would publish. Add your child's name, your town and your doctor's practice to that denylist (one per line).

## Troubleshooting

| Problem | Fix |
|---|---|
| `claude: command not found` | Open a new terminal; if it persists see [Fix your PATH](https://code.claude.com/docs/en/troubleshoot-install.md) |
| `ModuleNotFoundError: matplotlib` | Run `source .venv/bin/activate` first |
| `validate` lists problems | Each line names the field to fix; rerun setup or edit `private/profile.json` |
| Questionnaire didn't start | Type "run setup" in Claude Code |
| Page shows demo data after publishing | The `config/profile` document wasn't saved — repeat step 4 |
