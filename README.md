# Daily X intelligence briefing

Python 3.12 and GitHub Actions. No third-party Python dependencies. Uses **only the official X API v2** for source posts, OpenAI for analysis, and Resend for email. No scraped posts or fabricated fallback content.

## What runs

- **Overnight watch:** every available original post and reply, plus substantive quote posts, from `@AndreasSteno`, `@RaoulGMI`, and `@elonmusk`, from **9 PM the previous evening to 6:15 AM America/New_York**. Plain reposts are excluded. This search follows every pagination token without a page budget. A retrieval error stops delivery rather than presenting partial results as complete.
- **Previous-day top five:** AI ranks real posts from the previous **Eastern calendar day**, across crypto, rates, macro, AI, health, and electronic music. Five places cannot guarantee representation of all six areas. Each entry has an author, timestamp with EST/EDT, direct X link, attributed summary, and implication.
- **Scope:** the top five is a judgment over an explicit candidate pool, not a provable ranking of every post on X. Each topic uses English-language keyword search ordered by X relevancy, initially limited to two 100-post pages. Up to 30 posts per topic are preselected using engagement and recency, deduplicated, then ranked by the model. Each email discloses page counts and whether query pagination was exhausted. Adjust queries in `briefing.py` as interests evolve.
- API availability limits still apply: protected, deleted, withheld, unindexed posts, unavailable reply/quote context, and media-only information cannot be reconstructed. Text and returned quote/reply context are analyzed; images, audio, video and external pages are not fetched. Long AI inputs are explicitly limited; stored evidence preserves returned source text.

## Secure configuration

In [repository Actions settings](https://github.com/edgeworth27/Morning-Task/settings/secrets/actions), add these **secrets**:

| Secret | Value |
| --- | --- |
| `X_BEARER_TOKEN` | Your X developer app's Bearer Token with access to `/2/tweets/search/recent` |
| `AI_API_KEY` | OpenAI API key with access to your selected model |
| `RESEND_API_KEY` | Resend API key allowed to send from your verified domain |

An X API Key/Secret pair or user access token alone is not the app Bearer Token used here. Obtain that token in the X Developer console; do not put credentials in issues, chat, source files, or repository variables. Existing GitHub secret values cannot be read back. X access and usage credits, OpenAI billing, and a verified Resend sender are prerequisites. OpenAI API billing is separate from a ChatGPT subscription.

In [repository Actions variables](https://github.com/edgeworth27/Morning-Task/settings/variables/actions), configure:

| Variable | Value |
| --- | --- |
| `EMAIL_TO` | One recipient address |
| `EMAIL_FROM` | One Resend-verified sender, optionally `Daily Briefing <briefing@your-domain>` |
| `AI_MODEL` | Optional; default `gpt-4.1-mini`, must support structured JSON output |
| `TOPIC_PAGES` | Optional; default `2`, range `1`–`20` |
| `BRIEFING_ENABLED` | Set to `true` **after successful live validation** to enable daily scheduled delivery |

The workflow supplies its own short-lived `GITHUB_TOKEN`; no personal GitHub token is needed in Actions. It needs `contents: write` to maintain delivery state in the `briefing-state` branch. Organization policy must allow that permission. Keep this repository private if you want stored briefings and analysis to remain private. Sender and recipient addresses are not saved in the state branch (a hash is saved); the email content and provider message ID are stored there. Never put credentials in repository variables.

The cloud editor and GitHub Actions are separate runtimes. Adding a secret in cloud environment settings does **not** populate an Actions secret. For live testing in this cloud editor, securely configure the same three named bindings in environment settings and allow `api.x.com`, `api.openai.com`, `api.resend.com`, and `api.github.com`. Proxy-backed credentials must be used only through their intended HTTPS destination; do not copy placeholder values into GitHub secrets.

## Validate and activate

1. Run `python -m unittest discover -s tests -v`. These tests use **synthetic fixtures**. They verify DST, pagination, citation integrity, quote handling, error paths and duplicate-send recovery; they do not establish live API access or email delivery.
2. Open **Actions → Daily X intelligence → Run workflow** with `dry_run` enabled. The `date` input is the **briefing date in Eastern time**, not the date of the previous-day source posts. Leave it blank after today's 6:15 AM cutoff, or choose a recent past briefing date. This makes real, billable X and AI requests but sends no email. Inspect `briefing.json`, `.txt`, and `.html` in that run's artifact.
3. Run again with `dry_run` disabled. Confirm a successful Resend acceptance and message ID in the log, inspect the actual received email, and check the **delivered** status in Resend's email dashboard. Provider acceptance alone does not prove inbox delivery. If delivery is delayed, bounced or suppressed, correct the Resend/domain/recipient configuration before activation.
4. Set `BRIEFING_ENABLED=true`. Check that a scheduled run executes and that the email arrives. Enable GitHub's failed-workflow notifications for this repository; API outages, credit exhaustion, or rate limits cause a visible failed run, never a fake briefing. A failed day requires a manual rerun, using its briefing date, while still inside X recent-search retention.

The script rejects incomplete/future windows and dates beyond recent search's seven-day retention. It will never manufacture five entries when fewer eligible posts exist.

## Time and reliability

Actions cron is UTC: `15 10 * * *` and `15 11 * * *`. `zoneinfo("America/New_York")` selects exactly one slot according to the target day's offset. The inactive slot exits without calling X, OpenAI, or Resend. Calendar windows are built in Eastern time, so 23/25-hour DST days and the overnight clock transition are handled correctly. A delayed valid cron still runs after cutoff.

**6:15 AM is the scheduled start, not a guaranteed email arrival time.** GitHub Actions may queue, delay or drop scheduled jobs. Public-repository schedules may be disabled after inactivity. API retrieval and AI processing take additional time, and X indexing can lag. If guaranteed wall-clock delivery is required, use a scheduler with an operational SLA instead of GitHub Actions.

GitHub concurrency serializes runs. Before sending, the complete email payload is persisted in `briefing-state/deliveries/YYYY-MM-DD.json`; retries reuse the exact payload and Resend idempotency key. After acceptance, the provider ID is persisted. Already-sent days are skipped. If the final state write fails, rerun within 23 hours: Resend's 24-hour idempotency protection prevents a second send. An unresolved prepared record older than 23 hours stops for manual reconciliation in Resend, since blindly retrying could duplicate mail. Changing sender/recipient for an existing day also stops for review. Do not delete or edit delivery records to force a retry without checking provider status.

The workflow artifacts expire after seven days. Delivery records remain on the state branch. Topic retrieval can return up to `6 × TOPIC_PAGES × 100` posts per run, plus every overnight post and referenced context. X billing may count repeated/referenced reads differently; check your plan. AI calls include up to 180 ranking candidates plus overnight summaries in batches of 25. There is no paid API usage in the local test suite. Raising the topic budget increases usage and cost.

## Local development

Use the existing isolated checkout at `/workspace/Morning-Task`; no extra worktree is needed. Source credentials securely into your process without printing them. `.env` is ignored but **not automatically loaded**; `.env.example` contains names only.

```bash
cd /workspace/Morning-Task
python -m unittest discover -s tests -v
python briefing.py --dry-run
```

For delivery outside Actions, supply `GITHUB_TOKEN`, `GITHUB_REPOSITORY=edgeworth27/Morning-Task`, and `GITHUB_SHA` identifying an existing remote commit, plus the API credentials and email variables above. The GitHub token needs repository contents write access. Native Git proxy authentication in this editor does not establish GitHub REST API permission.

Useful official references: [X recent search](https://docs.x.com/x-api/posts/recent-search), [OpenAI structured outputs](https://platform.openai.com/docs/guides/structured-outputs), [Resend idempotency](https://resend.com/docs/dashboard/emails/idempotency-keys), [Actions schedule behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Deployment status

Read the task's final report for verified deployment and live-test results. A committed workflow, passing fixture tests, or accepted email does not independently establish active scheduling, live retrieval, or delivered mail. ChatGPT push notifications are not a supported destination for this GitHub Actions application; the chosen delivery is Resend email.
