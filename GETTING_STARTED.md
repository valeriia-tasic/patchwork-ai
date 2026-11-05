# Getting started

From a fresh clone to your own Patchwork running on your laptop: your profile, your log, your reports. About 15 minutes.

Everything here runs locally. Your answers and entries stay in `private/`, which git never sees.

---

## Prerequisites

Have these before you start:

| You need | Why | Check |
|---|---|---|
| A **Claude Pro, Max, Team or Enterprise** account | Claude Code, which runs the setup questionnaire and logs entries for you. The free plan doesn't include Claude Code. | Sign in at claude.ai |
| **Claude Code** installed | The agent that works inside this repo | `claude --version` |
| **Python 3.10 or newer** | The `patchwork` package does all counting and charting | `python3 --version` |
| **git** | To clone the repo | `git --version` |
| macOS, Linux, or Windows with WSL | Commands below are for a Bash/Zsh terminal | — |

No Claude account? Steps 2, 3 and 6 still work, and `python -m patchwork init` replaces the questionnaire in step 4. You'll edit `private/entries.json` by hand instead of asking Claude to log.

---

## 1. Install Claude Code and sign in

```bash
curl -fsSL https://claude.ai/install.sh | bash   # or: brew install --cask claude-code
claude --version                                  # prints a version number
```

The first time you run `claude`, it opens your browser to sign in with your Claude account. Full instructions: [Claude Code setup](https://code.claude.com/docs/en/setup).

## 2. Clone and install

```bash
git clone https://github.com/valeriia-tasic/patchwork-ai.git
cd patchwork-ai

python3 -m venv .venv
source .venv/bin/activate          # run this again in every new terminal
pip install -r requirements.txt

pytest -q                          # all tests should pass
```

## 3. Try the demo first (no setup needed)

The repo ships with a synthetic log for a fictional toddler, so you can see what you'll get before entering anything real.

```bash
# Sunday report: report.txt, report.html and two charts in out/
python -m patchwork weekly  --entries data/sample_entries.json --today 2025-05-18 --out out

# Nightly check: prints the alerts that would be pushed (empty on a quiet night)
python -m patchwork nightly --entries data/sample_entries.json --today 2025-05-18

# The phone log page, read-only demo
python -m http.server 8000         # open http://localhost:8000/web/ , Ctrl+C to stop
```

Open `out/report.html` and `out/chart-areas.png` to see the report.

## 4. Set up your profile

Start Claude Code in the repo folder:

```bash
claude
```

Because there's no `private/profile.json` yet, Claude starts the first-use questionnaire ([`SETUP.md`](SETUP.md)) on its own. If it doesn't, type **"run setup"**. It asks one topic at a time:

1. Body areas you track, and which smaller spots roll up into them (elbows → Arms)
2. What "full body" covers
3. Each cream: name, where it's used, once a day or Morning / Night, and optional alert limits
4. Your antihistamine: brand and optional alert limit
5. Whether to log allergen exposure
6. Email, timezone, report day

Limits are optional and come from **your doctor's instructions**. Patchwork never suggests one; leave a limit blank and nothing alerts for it.

Claude saves `private/profile.json` and checks it. To check it yourself:

```bash
python -m patchwork validate       # prints "ok"
```

No Claude Code? Run `python -m patchwork init` for the same questions in the terminal.

## 5. Log entries

With Claude Code open in the repo, just tell it what you did:

> "Hydrocortisone on arms and legs today"
> "Gave Zyrtec at 7:30pm"
> "Peanut, 1/12 serving at lunch"
> "Flare on her neck, after swimming"

Claude adds each one to `private/entries.json` and confirms in one line. You can also edit the file directly; each entry looks like this:

```json
[
  {"type": "hydrocortisone", "day": "2026-11-05", "areas": ["Arms", "Legs"]},
  {"type": "anti", "day": "2026-11-05", "at": "2026-11-05T19:30:00"},
  {"type": "allergen", "day": "2026-11-05", "at": "2026-11-05T12:00:00", "allergen": "Peanut", "amount": "1/12 serving"},
  {"type": "flare", "day": "2026-11-05", "areas": ["Neck"], "note": "after swimming"}
]
```

`type` is a cream id from your profile (shown by `validate` and in `private/profile.json`), or `anti`, `flare`, `allergen` or `note`.

Have past records? Paste them into Claude and ask it to import them; it confirms the count before saving.

## 6. Run your reports

```bash
mkdir -p private/out
python -m patchwork weekly  --entries private/entries.json --out private/out
python -m patchwork nightly --entries private/entries.json
```

Or ask Claude: **"Run this week's report"** or **"Any alerts tonight?"** Claude runs the same commands and explains the result. It never counts by hand.

Reports use your profile automatically and default to today. Add `--today YYYY-MM-DD` to look at another week.

## 7. Optional: run it on a schedule

To get the nightly check and Sunday report without remembering, add them to your crontab (`crontab -e`). Replace the path with where you cloned the repo:

```cron
# Nightly check at 8pm; alerts saved to private/out/nightly.json
0 20 * * * cd /path/to/patchwork-ai && .venv/bin/python -m patchwork nightly --entries private/entries.json > private/out/nightly.json 2>&1

# Sunday report at 8pm
0 20 * * 0 cd /path/to/patchwork-ai && .venv/bin/python -m patchwork weekly --entries private/entries.json --out private/out
```

Cron only runs while your computer is awake. Next morning, ask Claude "what did last night's check find?" and it reads `private/out/nightly.json`.

## 8. Optional: phone logging and cloud agents

The author's own setup goes further: a one-tap log page on the phone, a push notification at 8pm, and the Sunday report emailed with charts, all running in the cloud whether or not a laptop is on. It uses Claude features beyond Claude Code (published artifacts with storage, scheduled tasks, and a Gmail connector), so availability depends on your plan.

The pieces are in the repo:

- `web/index.html`: the log page. Publish it as a Claude artifact with a database, then save your `private/profile.json` into it as the `config/profile` document. The page reads its buttons and areas from there.
- `prompts/nightly.md` and `prompts/weekly.md`: the two scheduled-agent prompts. Fill in the `{{…}}` placeholders and create them as scheduled tasks. Each run clones this repo and runs `python -m patchwork`, so all the rules stay in the code.

Ask Claude to walk you through it; it has this guide and the repo for context.

---

## Before you push anything

If you fork this repo and commit changes, run `pytest -q` first. `tests/test_privacy.py` fails the build if an email address, a private link, or any term from your own `private/denylist.txt` appears in a file git would publish. Add your child's name, your town and your doctor's practice to that denylist (one per line).

## Troubleshooting

| Problem | Fix |
|---|---|
| `claude: command not found` | Open a new terminal; if it persists see [Fix your PATH](https://code.claude.com/docs/en/troubleshoot-install.md) |
| `ModuleNotFoundError: matplotlib` | The virtual environment isn't active: `source .venv/bin/activate` |
| `validate` lists problems | Each line names the field to fix; edit `private/profile.json` or rerun setup |
| Report says 0 for everything | The `type` in your entries doesn't match a cream id in your profile, or `--today` is outside your data |
| Questionnaire didn't start | Type "run setup" in Claude Code |
