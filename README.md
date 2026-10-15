# Daily X intelligence briefing

Python 3.12 and GitHub Actions. No third-party Python dependencies. Uses **only the official X API v2** for source posts, OpenAI for analysis, and Telegram Bot API for private chat delivery. No scraped posts or fabricated fallback content.

## What runs

- **Overnight watch:** every available original post and reply, plus substantive quote posts, from `@AndreasSteno`, `@RaoulGMI`, and `@elonmusk`, from **9 PM the previous evening to 6:15 AM America/New_York**. Plain reposts are excluded. This search follows every pagination token without a page budget. An error affecting requested posts stops delivery rather than presenting partial results as complete. Unavailable quoted/replied-to references are explicitly labeled and counted; their contents are never inferred. Missing AI batch summaries are recovered using smaller requests, with complete ID coverage required before delivery. All posts are still retrieved for evidence, but **Elon Musk is shown only when directly relevant to crypto, rates, macro, AI, health, electronic music, or material Tesla/SpaceX business developments**. This applies to replies and top-five selections too. Material Tesla/SpaceX updates are explicitly included for a shareholder: production/deliveries, earnings/margins, contracts, financing, regulatory/safety risks, Starlink developments and consequential launch milestones/failures. Jokes, unrelated personal/partisan remarks and routine promotion or launch announcements remain excluded; the other two accounts retain their original coverage.
- **Previous-day top five:** AI ranks real posts from the previous **Eastern calendar day**, across crypto, rates, macro, AI, health, electronic music, Tesla, and SpaceX. Five places cannot guarantee representation of all eight areas. Each entry has an author, timestamp with EST/EDT, direct X link, attributed summary, and implication.
- **Scope:** the top five is a judgment over an explicit candidate pool, not a provable ranking of every post on X. Each topic uses English-language keyword search ordered by X relevancy, initially limited to two 100-post pages. Up to 30 posts per topic are preselected using engagement and recency, deduplicated, then ranked by the model. Each briefing discloses page counts and whether query pagination was exhausted. Adjust queries in `briefing.py` as interests evolve.
- API availability limits still apply: protected, deleted, withheld, unindexed posts, unavailable reply/quote context, and media-only information cannot be reconstructed. Text and returned quote/reply context are analyzed; images, audio, video and external pages are not fetched. Long AI inputs are explicitly limited; stored evidence preserves returned source text.

## Secure configuration

In [repository Actions settings](https://github.com/edgeworth27/Morning-Task/settings/secrets/actions), add these **secrets**:

| Secret | Value |
| --- | --- |
| `X_BEARER_TOKEN` | Your X developer app's Bearer Token with access to `/2/tweets/search/recent` |
| `AI_API_KEY` | OpenAI API key with access to your selected model |
| `TELEGRAM_BOT_TOKEN` | Bot token issued by Telegram’s official @BotFather |
| `TELEGRAM_CHAT_ID` | Your private chat ID, found using the setup workflow below |

An X API Key/Secret pair or user access token alone is not the app Bearer Token used here. Obtain that token in the X Developer console; do not put credentials in issues, chat, source files, or repository variables. Existing GitHub secret values cannot be read back. X access and usage credits, OpenAI billing, and a Telegram bot are prerequisites. OpenAI API billing is separate from a ChatGPT subscription.

In [repository Actions variables](https://github.com/edgeworth27/Morning-Task/settings/variables/actions), configure:

| Variable | Value |
| --- | --- |
| `AI_MODEL` | Optional; default `gpt-4.1-mini`, must support structured JSON output |
| `TOPIC_PAGES` | Optional; default `2`, range `1`–`20` |

The workflow supplies its own short-lived `GITHUB_TOKEN`; no personal GitHub token is needed in Actions. It needs `contents: write` to maintain delivery state in the `briefing-state` branch. Organization policy must allow that permission. Keep this repository private if you want stored briefings and analysis to remain private. The private chat ID is not saved in the state branch (a hash is saved); briefing text and Telegram message IDs are stored there. Never put credentials in repository variables.

The cloud editor and GitHub Actions are separate runtimes. Adding a secret in cloud environment settings does **not** populate an Actions secret. Run Telegram setup and live delivery tests in Actions, where the bot token is available directly to the application. Cloud network access needs `api.x.com`, `api.openai.com`, `api.telegram.org`, and `api.github.com` for corresponding operations. Proxy-backed credentials must be used only through their supported route; Telegram embeds the token in the request path, so do not assume a proxy placeholder is a usable bot token. Do not copy placeholder values into GitHub secrets.

## Connect your Telegram chat

1. In Telegram, open the official [@BotFather](https://t.me/BotFather). Send `/newbot`, then follow its prompts to choose a bot name and username. Save its token in GitHub as the **Actions secret** `TELEGRAM_BOT_TOKEN`. Never paste the token in chat, a browser URL, or an issue.
2. Open your newly created bot using the link BotFather provides. Tap **Start** (or send `/start`) in a private chat. Bots cannot initiate a conversation until you start it.
3. In this repository’s **Actions → Daily X intelligence → Run workflow**, check **find_chat_id**. This setup-only run calls `getUpdates`, prints the numeric private chat ID, and sends no message. It does not require X/OpenAI credentials. Use a new dedicated bot with no webhook; if updates are empty, send `/start` again and retry.
4. Open that run’s **Retrieve, summarize, and deliver** log. Copy the printed number into a new repository **Actions secret** named `TELEGRAM_CHAT_ID`. The helper requires exactly one private `/start` chat to avoid guessing the recipient.
5. Add `X_BEARER_TOKEN` and `AI_API_KEY` if you have not already. Run the live validations below, leaving **find_chat_id** unchecked.

## Validate and activate

1. Run `python -m unittest discover -s tests -v`. These tests use **synthetic fixtures**. They verify DST, pagination, citation integrity, quote handling, error paths and duplicate-send recovery; they do not establish live API access or Telegram delivery.
2. Open **Actions → Daily X intelligence → Run workflow** with `dry_run` enabled. The `date` input is the **briefing date in Eastern time**, not the date of the previous-day source posts. Leave it blank after today's 6:15 AM cutoff, or choose a recent past briefing date. This makes real, billable X and AI requests but sends no Telegram messages. Inspect `briefing.json`, `.txt`, and `.html` in that run's artifact.
3. Run again with `dry_run` disabled. Confirm that Telegram accepted the messages and inspect the actual briefing in your bot’s private chat. API acceptance does not prove that a phone notification was displayed; ensure the chat is unmuted and Telegram notifications are enabled on your device.
4. Daily scheduling is enabled in the deployed workflow after live delivery validation. To pause it, use **Actions → Daily X intelligence → ⋯ → Disable workflow**; re-enable it from the same page. No enablement repository variable is needed. Check that a scheduled run executes and that the Telegram briefing arrives. Enable GitHub's failed-workflow notifications for this repository; API outages, credit exhaustion, or rate limits cause a visible failed run, never a fake briefing. A failed day requires a manual rerun, using its briefing date, while still inside X recent-search retention.

The script rejects incomplete/future windows and dates beyond recent search's seven-day retention. It will never manufacture five entries when fewer eligible posts exist.

## Time and reliability

Actions cron is UTC: `15 10 * * *` and `15 11 * * *`. `zoneinfo("America/New_York")` selects exactly one slot according to the target day's offset. The inactive slot exits without calling X, OpenAI, or Telegram. Calendar windows are built in Eastern time, so 23/25-hour DST days and the overnight clock transition are handled correctly. A delayed valid cron still runs after cutoff.

**6:15 AM is the scheduled start, not a guaranteed notification arrival time.** GitHub Actions may queue, delay or drop scheduled jobs. Public-repository schedules may be disabled after inactivity. API retrieval and AI processing take additional time, and X indexing can lag. If guaranteed wall-clock delivery is required, use a scheduler with an operational SLA instead of GitHub Actions.

GitHub concurrency serializes runs. Before sending, the exact message parts are persisted in `briefing-state/deliveries/YYYY-MM-DD.json`. Telegram has **no idempotency key**. Each part is marked `sending` before the API call and acknowledged with its message ID afterward. If a crash/network error leaves a `sending` record, reruns stop for manual reconciliation instead of risking a duplicate. Check the bot chat and the record’s zero-based `sending_part`: if it arrived, add its Telegram message ID to `message_ids`; if it did not arrive, leave that list unchanged. Set status to `prepared` and `sending_part` to null only after establishing the outcome. Then rerun the same briefing date. If the outcome cannot be established, do not retry that part. A failure after all parts were acknowledged can resume without sending again. Changing chat for an existing day stops for review. Complete `sent` records are skipped.

Briefings put the top five first, followed by the overnight watch. Summaries use one short sentence and a short implication, with blank space between entries, bold section headings, compact timestamps, and clickable “View post” links. Verbose retrieval diagnostics remain in the JSON artifact instead of filling the chat. Long briefings are split into numbered HTML-formatted messages below Telegram’s size limit, preserving source-link lines and handling emoji conservatively. Parts are paced to avoid per-chat rate limits. Link previews are disabled. No email account, Resend key, sender domain, or DNS setup is needed.

The workflow artifacts expire after seven days. Delivery records remain on the state branch. Topic retrieval can return up to `8 × TOPIC_PAGES × 100` posts per run, plus every overnight post and referenced context. X billing may count repeated/referenced reads differently; check your plan. AI calls include up to 240 ranking candidates plus overnight summaries in batches of 25. There is no paid API usage in the local test suite. Raising the topic budget increases usage and cost.

## Local development

Use the existing isolated checkout at `/workspace/Morning-Task`; no extra worktree is needed. Source credentials securely into your process without printing them. `.env` is ignored but **not automatically loaded**; `.env.example` contains names only.

```bash
cd /workspace/Morning-Task
python -m unittest discover -s tests -v
python briefing.py --dry-run
```

For delivery outside Actions, supply `GITHUB_TOKEN`, `GITHUB_REPOSITORY=edgeworth27/Morning-Task`, and `GITHUB_SHA` identifying an existing remote commit, plus the API credentials and Telegram secrets above. The GitHub token needs repository contents write access. Native Git proxy authentication in this editor does not establish GitHub REST API permission.

Useful official references: [X recent search](https://docs.x.com/x-api/posts/recent-search), [OpenAI structured outputs](https://platform.openai.com/docs/guides/structured-outputs), [Telegram Bot API](https://core.telegram.org/bots/api#sendmessage), [Actions schedule behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Deployment status

Read the task's final report for verified deployment and live-test results. A committed workflow, passing fixture tests, or accepted message does not independently establish active scheduling, live retrieval, or delivered mail. ChatGPT push notifications are not a supported destination for this GitHub Actions application; the chosen delivery is Telegram.
