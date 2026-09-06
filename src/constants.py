"""User-facing text and static constants. No secrets live here."""

CONSENT_TEXT = (
    "🔐 <b>Session String Generator — Privacy & Consent Notice</b>\n\n"
    "This bot helps you generate a Telegram <b>client session</b> "
    "(Telethon or Pyrogram) for <u>your own Telegram account only</u>.\n\n"
    "A session string or session file is equivalent to your account login — "
    "anyone who has it can access your account without your password. "
    "By continuing you confirm that:\n\n"
    "• You are generating this session for <b>your own account</b>.\n"
    "• You understand the resulting session grants <b>full account access</b> "
    "and must <b>never be shared</b> with anyone, pasted into "
    "public chats, or sent to third-party bots.\n"
    "• You will store it securely (e.g. an encrypted secret manager).\n"
    "• You can revoke it anytime via "
    "<b>Telegram → Settings → Devices → Revoke</b>.\n\n"
    "This bot does not store your session, phone number, code, password, "
    "or API credentials. Everything is wiped from memory as soon as the "
    "flow ends, fails, is cancelled, or times out.\n\n"
    "Do you consent and wish to continue?"
)

CANCEL_HINT = "\n\nSend /cancel at any time to stop and securely erase this session."

ASK_CLIENT_TYPE = "Which client library do you want the session for?"
ASK_OUTPUT_TYPE = "Which output format do you want?"

ASK_API_ID = (
    "Send your <b>API ID</b> (a number).\n"
    "Get it from <a href='https://my.telegram.org'>my.telegram.org</a> → "
    "API Development Tools." + CANCEL_HINT
)
ASK_API_HASH = "Now send your <b>API Hash</b> (32-character hex string)." + CANCEL_HINT
ASK_PHONE = (
    "Send your phone number in international format, e.g. <code>+15551234567</code>.\n"
    "This is used only to request a login code for your own account, in this "
    "chat, and is deleted right after the flow ends." + CANCEL_HINT
)
ASK_CODE = (
    "Telegram just sent a login code to your account. "
    "Enter it using the keypad below (do <b>not</b> type it as a normal "
    "message elsewhere, and never paste it into any other bot or chat)."
    + CANCEL_HINT
)
ASK_PASSWORD = (
    "Your account has Two-Step Verification enabled. "
    "Send your cloud password now (message will be deleted immediately after processing)."
    + CANCEL_HINT
)

SESSION_STRING_WARNING = (
    "⚠️ <b>Keep this secret.</b> Anyone with this string has full access to "
    "your account. Never share it, never paste it into a bot or website, "
    "and store it only in a secure secret manager.\n\n"
    "If you ever suspect it has leaked, revoke it immediately via "
    "<b>Telegram → Settings → Devices → Revoke</b>."
)

CANCELLED_TEXT = "🧹 Operation cancelled. All temporary data has been securely erased."
TIMEOUT_TEXT = (
    "⌛ Your session generation timed out due to inactivity. "
    "All temporary data has been securely erased. Send /start to try again."
)
RATE_LIMITED_TEXT = (
    "🚦 You've started too many flows recently. Please wait a bit before trying again."
)
ALREADY_ACTIVE_TEXT = (
    "You already have an active session-generation flow. "
    "Send /cancel to stop it before starting a new one."
)
PRIVATE_ONLY_TEXT = "This bot only works in a private chat with it. Please message it directly."
NOT_ALLOWED_TEXT = "You are not authorized to use this bot."

CODE_DIGITS_MAX = 6
