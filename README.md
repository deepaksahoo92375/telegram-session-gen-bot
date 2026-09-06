# Telegram Session String Generator Bot

A private-use aiogram 3 bot that lets a user generate a **Telethon** or
**Pyrogram** session (string or file) **for their own Telegram account**,
with explicit consent, no persistence, and aggressive in-memory cleanup.

## What this bot does NOT do

- It does not process accounts other than the requesting user's own.
- It does not support bulk/automated account processing or account lists.
- It does not store generated sessions, API credentials, phone numbers,
  codes, or passwords in any database or file beyond the lifetime of the
  active flow.
- It does not log secrets. Logging is filtered through a redaction layer.
- It only works in private 1:1 chats.

## 1. Prerequisites

- Python 3.12+
- A Telegram bot token from **@BotFather**
- Your own personal `api_id` / `api_hash` from https://my.telegram.org
  (each end user supplies their own during the flow — the bot operator
  does not need these)

## 2. Get a bot token from BotFather

1. Open a chat with **@BotFather** on Telegram.
2. Send `/newbot` and follow the prompts (name, username).
3. Copy the token it gives you into `BOT_TOKEN` in your `.env`.
4. Optional but recommended: send `/setprivacy` → select your bot → leave
   privacy **Enabled** (default), since this bot only needs private-chat
   messages anyway.
5. Optional: `/setjoingroups` → **Disable**, since this bot is private-chat only.

## 3. Get your own API ID / API Hash (each user does this for themselves)

1. Go to https://my.telegram.org and log in with your phone number.
2. Click **API Development Tools**.
3. Fill in the form (app title/short name can be anything, e.g. "My Session Tool").
4. Copy the `api_id` and `api_hash` shown — you'll paste these into the bot
   when it asks, not into `.env`.

## 4. Local installation

```bash
git clone <this-repo> telegram-session-bot
cd telegram-session-bot
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and set BOT_TOKEN (and any other overrides)
python -m src.main
```

## 5. Docker deployment

```bash
cp .env.example .env
# edit .env and set BOT_TOKEN
docker compose up --build -d
docker compose logs -f
```

The compose file mounts the secure temp directory as an in-memory `tmpfs`
and runs the container filesystem read-only, so no session data ever
touches persistent disk.

## 6. Using the bot

1. Send `/start` in a private chat with your bot.
2. Read and accept the privacy/consent notice.
3. Choose **Telethon** or **Pyrogram**, then **String** or **File**.
4. Enter your own `api_id` and `api_hash` (from my.telegram.org).
5. Enter your phone number in international format (e.g. `+15551234567`).
6. Telegram sends a login code to your **Telegram app** (not this bot).
   Enter it using the inline keypad (or type digits separated by spaces).
7. If Two-Step Verification is enabled, enter your cloud password when asked.
8. The bot sends your session string or session file **in this same chat**,
   with a warning to keep it secret.
9. All credentials, the phone number, the code, the password, and any
   temporary files are wiped from memory/disk immediately afterward.

Send `/cancel` at any point to abort and securely erase the current flow.

## 7. Revoking a session you generated

If you ever want to invalidate a session string/file you generated (e.g.
you suspect it leaked, or you're done using it):

1. Open Telegram → **Settings → Devices**.
2. Find the corresponding active session (it will show as a generic MTProto
   session, similar to other logged-in devices).
3. Tap it and select **Terminate session**.

Do this immediately if you ever believe a session string has been exposed.

## 8. Configuration reference (`.env`)

| Variable | Description | Default |
|---|---|---|
| `BOT_TOKEN` | Token from BotFather | — (required) |
| `ALLOWED_USER_IDS` | Comma-separated numeric user IDs allowed to use the bot; empty = anyone in a private chat | empty |
| `RATE_LIMIT_MAX_STARTS` | Max flow starts per user per window | 3 |
| `RATE_LIMIT_WINDOW_SECONDS` | Window for the above | 600 |
| `MAX_AUTH_ATTEMPTS` | Max wrong code/password attempts before auto-cancel | 3 |
| `FLOW_TIMEOUT_SECONDS` | Inactivity timeout before a flow is wiped | 300 |
| `SECURE_TMP_DIR` | Local path for ephemeral session files | `/tmp/tgsession_secure` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

## 9. Security notes

- **Never** set `LOG_LEVEL=DEBUG` in production — third-party library debug
  logs can be verbose; the redaction filter is a safety net, not a license
  to log secrets on purpose.
- The bot process holds decrypted credentials and the resulting session
  only in memory, for the duration of one flow, and calls a full cleanup
  routine on success, failure, cancellation, timeout, and process shutdown.
- Session files/strings are sent with `protect_content=True` (where
  supported) to make Telegram-side forwarding harder from the bot's message
  — the ultimate protection is the user immediately moving the value to a
  secure secret store and never re-sharing it.
- The bot enforces private-chat-only via middleware and never has admin
  access to, or storage of, generated sessions.
- Rate limiting and a single-active-flow-per-user rule are enforced in
  process memory; consider running the bot on infrastructure you trust,
  since anyone with access to the running process (not the chat) could see
  in-memory ephemeral state on that host in a memory dump — this is
  inherent to any tool that must materialize a session locally to create it.

## 10. Test checklist

Run the automated tests:

```bash
pip install -r requirements.txt
pytest -v
```

Automated coverage includes:
- [ ] Validators reject malformed API ID / API hash / phone / code / password
- [ ] Redaction strips phone numbers, API-hash-like tokens, and long tokens from text/exceptions
- [ ] Cleanup disconnects clients, wipes temp files from disk, and clears in-memory dicts
- [ ] Rate limiter enforces per-user sliding-window limits and resets correctly
- [ ] SessionManager enforces one active flow per user, expires idle flows, and wipes all flows on shutdown

Manual checklist before real-world use:
- [ ] Bot only responds in private chats (test from a group — it should stay silent)
- [ ] `/cancel` works from every state and clears the FSM + temp files
- [ ] Invalid API ID/hash surfaces a clear error and ends the flow
- [ ] Invalid phone number surfaces a clear error and ends the flow
- [ ] FloodWait from Telegram is surfaced with the wait time and ends the flow
- [ ] Wrong code 3x (or your configured `MAX_AUTH_ATTEMPTS`) auto-cancels
- [ ] 2FA-enabled account correctly prompts for password
- [ ] Wrong password 3x auto-cancels
- [ ] Idle for longer than `FLOW_TIMEOUT_SECONDS` auto-expires with a notification
- [ ] Generated Telethon string session actually authenticates via a throwaway test script
- [ ] Generated Pyrogram string session actually authenticates via a throwaway test script
- [ ] Generated Telethon/Pyrogram session **file** loads correctly in each respective library
- [ ] No secrets appear in stdout/stderr logs during a full run (grep logs for the phone/api_hash you used)
- [ ] Temp directory is empty after each completed/cancelled/timed-out flow
- [ ] Revoking the generated session via Telegram Settings → Devices actually invalidates it
