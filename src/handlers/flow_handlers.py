"""The full interactive session-generation flow.

State machine:
    consent -> choose client -> choose output -> api_id -> api_hash ->
    phone -> code (inline keypad) -> [password if 2FA] -> generate -> send -> cleanup
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from src.clients.errors import (
    ClientAdapterError,
    CodeExpiredError,
    FloodWaitErrorNormalized,
    InvalidCodeError,
    InvalidCredentialsError,
    InvalidPasswordError,
    InvalidPhoneError,
    PasswordRequiredError,
)
from src.clients.pyrogram_adapter import PyrogramAdapter
from src.clients.telethon_adapter import TelethonAdapter
from src.config import Settings
from src.constants import (
    ALREADY_ACTIVE_TEXT,
    ASK_API_HASH,
    ASK_API_ID,
    ASK_CLIENT_TYPE,
    ASK_CODE,
    ASK_OUTPUT_TYPE,
    ASK_PASSWORD,
    ASK_PHONE,
    RATE_LIMITED_TEXT,
    SESSION_STRING_WARNING,
)
from src.flow.session_manager import SessionManager
from src.security.redaction import redact_exception
from src.security.secure_files import secure_temp_dir
from src.states import SessionFlow
from src.validation.validators import (
    ValidationError,
    validate_api_hash,
    validate_api_id,
    validate_code,
    validate_password,
    validate_phone,
)

logger = logging.getLogger(__name__)

router = Router(name="flow")


def _client_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Telethon", callback_data="client:telethon"),
                InlineKeyboardButton(text="Pyrogram", callback_data="client:pyrogram"),
            ]
        ]
    )


def _output_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="String", callback_data="output:string"),
                InlineKeyboardButton(text="File", callback_data="output:file"),
            ]
        ]
    )


def _code_keypad(entered_len: int) -> InlineKeyboardMarkup:
    digit_rows = [
        [InlineKeyboardButton(text=str(d), callback_data=f"digit:{d}") for d in row]
        for row in ((1, 2, 3), (4, 5, 6), (7, 8, 9))
    ]
    digit_rows.append(
        [
            InlineKeyboardButton(text="⌫ Back", callback_data="digit:back"),
            InlineKeyboardButton(text="0", callback_data="digit:0"),
            InlineKeyboardButton(text="✅ Submit", callback_data="digit:submit"),
        ]
    )
    dots = "●" * entered_len + "○" * max(0, 6 - entered_len)
    digit_rows.insert(0, [InlineKeyboardButton(text=dots, callback_data="digit:noop")])
    return InlineKeyboardMarkup(inline_keyboard=digit_rows)


# ---------------------------------------------------------------------------
# Consent -> client choice
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "consent:yes", SessionFlow.awaiting_consent)
async def consent_accepted(callback: CallbackQuery, state: FSMContext, manager: SessionManager) -> None:
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    ok, reason = manager.try_start_flow(user_id, chat_id)
    if not ok:
        text = ALREADY_ACTIVE_TEXT if reason == "already_active" else RATE_LIMITED_TEXT
        await callback.message.edit_text(text)
        await state.clear()
        await callback.answer()
        return
    await state.set_state(SessionFlow.choosing_client)
    await callback.message.edit_text(ASK_CLIENT_TYPE, reply_markup=_client_choice_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("client:"), SessionFlow.choosing_client)
async def choose_client(callback: CallbackQuery, state: FSMContext, manager: SessionManager) -> None:
    user_id = callback.from_user.id
    flow = manager.get_flow(user_id)
    if flow is None:
        await callback.answer("Session expired, send /start again.", show_alert=True)
        return
    flow.client_type = callback.data.split(":", 1)[1]
    await state.set_state(SessionFlow.choosing_output)
    await callback.message.edit_text(ASK_OUTPUT_TYPE, reply_markup=_output_choice_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("output:"), SessionFlow.choosing_output)
async def choose_output(callback: CallbackQuery, state: FSMContext, manager: SessionManager) -> None:
    user_id = callback.from_user.id
    flow = manager.get_flow(user_id)
    if flow is None:
        await callback.answer("Session expired, send /start again.", show_alert=True)
        return
    flow.output_type = callback.data.split(":", 1)[1]
    await state.set_state(SessionFlow.entering_api_id)
    await callback.message.edit_text(ASK_API_ID, disable_web_page_preview=True)
    await callback.answer()


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

@router.message(SessionFlow.entering_api_id)
async def receive_api_id(message: Message, state: FSMContext, manager: SessionManager) -> None:
    flow = manager.get_flow(message.from_user.id)
    if flow is None:
        await message.answer(ALREADY_ACTIVE_TEXT)
        return
    try:
        flow.api_id = validate_api_id(message.text or "")
    except ValidationError as exc:
        await message.answer(str(exc))
        return
    finally:
        await _delete_silently(message)
    await state.set_state(SessionFlow.entering_api_hash)
    await message.answer(ASK_API_HASH)


@router.message(SessionFlow.entering_api_hash)
async def receive_api_hash(message: Message, state: FSMContext, manager: SessionManager) -> None:
    flow = manager.get_flow(message.from_user.id)
    if flow is None:
        await message.answer(ALREADY_ACTIVE_TEXT)
        return
    try:
        flow.api_hash = validate_api_hash(message.text or "")
    except ValidationError as exc:
        await message.answer(str(exc))
        return
    finally:
        await _delete_silently(message)
    await state.set_state(SessionFlow.entering_phone)
    await message.answer(ASK_PHONE)


@router.message(SessionFlow.entering_phone)
async def receive_phone(
    message: Message, state: FSMContext, manager: SessionManager, settings: Settings
) -> None:
    flow = manager.get_flow(message.from_user.id)
    if flow is None:
        await message.answer(ALREADY_ACTIVE_TEXT)
        return
    try:
        phone = validate_phone(message.text or "")
    except ValidationError as exc:
        await message.answer(str(exc))
        return
    finally:
        await _delete_silently(message)

    flow.phone = phone
    await message.answer("Requesting a login code from Telegram, one moment…")

    try:
        adapter = await _build_and_connect_adapter(flow, settings)
        flow.adapter = adapter
        await adapter.send_code(phone)
    except InvalidCredentialsError:
        await message.answer(
            "Your API ID/API Hash was rejected by Telegram. "
            "Send /cancel and try again with valid credentials."
        )
        await manager.end_flow(message.from_user.id)
        await state.clear()
        return
    except InvalidPhoneError:
        await message.answer("That phone number was rejected by Telegram. Please /cancel and try again.")
        await manager.end_flow(message.from_user.id)
        await state.clear()
        return
    except FloodWaitErrorNormalized as exc:
        await message.answer(str(exc))
        await manager.end_flow(message.from_user.id)
        await state.clear()
        return
    except ClientAdapterError:
        await message.answer("Something went wrong contacting Telegram. Please /cancel and try again.")
        await manager.end_flow(message.from_user.id)
        await state.clear()
        return
    except Exception as exc:
        logger.error("Unexpected error requesting code: %s", redact_exception(exc))
        await message.answer("An unexpected error occurred. Please /cancel and try again.")
        await manager.end_flow(message.from_user.id)
        await state.clear()
        return

    await state.set_state(SessionFlow.entering_code)
    await message.answer(ASK_CODE, reply_markup=_code_keypad(0))


async def _build_and_connect_adapter(flow, settings: Settings):
    assert flow.api_id is not None and flow.api_hash is not None
    if flow.client_type == "telethon":
        session_path = None
        if flow.output_type == "file":
            temp_dir = _enter_secure_temp_dir(flow, settings)
            session_path = temp_dir / "telethon_session"
        adapter = TelethonAdapter(flow.api_id, flow.api_hash, session_file_path=session_path)
    else:
        workdir = None
        if flow.output_type == "file":
            workdir = _enter_secure_temp_dir(flow, settings)
        adapter = PyrogramAdapter(
            flow.api_id,
            flow.api_hash,
            workdir=workdir,
            in_memory=(flow.output_type == "string"),
        )
    await adapter.connect()
    return adapter


def _enter_secure_temp_dir(flow, settings: Settings):
    """Open a secure_temp_dir() context manager and keep it alive for the
    lifetime of the flow; the underlying directory is force-removed in
    SessionManager.end_flow() via wipe_temp_files/shred_file on its contents
    and an explicit rmtree registered on the flow."""
    ctx = secure_temp_dir(settings.secure_tmp_dir)
    temp_dir = ctx.__enter__()
    flow.temp_dir = temp_dir
    flow._temp_dir_ctx = ctx  # noqa: SLF001 - internal bookkeeping only
    return temp_dir


# ---------------------------------------------------------------------------
# Code entry via inline keypad (avoids Telegram flagging a typed code message)
# ---------------------------------------------------------------------------

_pending_code: dict[int, str] = {}


@router.callback_query(F.data.startswith("digit:"), SessionFlow.entering_code)
async def handle_digit(
    callback: CallbackQuery, state: FSMContext, manager: SessionManager, settings: Settings
) -> None:
    user_id = callback.from_user.id
    flow = manager.get_flow(user_id)
    if flow is None:
        await callback.answer("Session expired, send /start again.", show_alert=True)
        return

    action = callback.data.split(":", 1)[1]
    current = _pending_code.get(user_id, "")

    if action == "noop":
        await callback.answer()
        return
    if action == "back":
        current = current[:-1]
    elif action == "submit":
        await _submit_code(callback, state, manager, settings, current)
        return
    elif action.isdigit() and len(current) < 6:
        current += action

    _pending_code[user_id] = current
    await callback.message.edit_reply_markup(reply_markup=_code_keypad(len(current)))
    await callback.answer()


@router.message(SessionFlow.entering_code)
async def handle_code_text(
    message: Message, state: FSMContext, manager: SessionManager, settings: Settings
) -> None:
    """Fallback: allow typing the code as separated digits, e.g. '1 2 3 4 5'."""
    flow = manager.get_flow(message.from_user.id)
    if flow is None:
        await message.answer(ALREADY_ACTIVE_TEXT)
        return
    try:
        code = validate_code(message.text or "")
    except ValidationError as exc:
        await message.answer(str(exc))
        return
    finally:
        await _delete_silently(message)
    await _process_code(message.from_user.id, message.chat.id, state, manager, settings, code, message)


async def _submit_code(callback: CallbackQuery, state, manager: SessionManager, settings: Settings, code: str) -> None:
    user_id = callback.from_user.id
    _pending_code.pop(user_id, None)
    try:
        validated = validate_code(code)
    except ValidationError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.answer()
    await _process_code(user_id, callback.message.chat.id, state, manager, settings, validated, callback.message)


async def _process_code(user_id, chat_id, state, manager: SessionManager, settings: Settings, code: str, reply_target) -> None:
    flow = manager.get_flow(user_id)
    if flow is None or flow.adapter is None:
        await reply_target.answer("Session expired, send /start again.")
        return

    try:
        await flow.adapter.sign_in_with_code(code)
    except PasswordRequiredError:
        await state.set_state(SessionFlow.entering_password)
        await reply_target.answer(ASK_PASSWORD)
        return
    except (InvalidCodeError, CodeExpiredError) as exc:
        flow.auth_attempts += 1
        if flow.auth_attempts >= settings.max_auth_attempts:
            await reply_target.answer("Too many invalid attempts. Cancelling for your security.")
            await manager.end_flow(user_id)
            await state.clear()
            return
        await reply_target.answer(f"{exc} Please try again using the keypad.", reply_markup=_code_keypad(0))
        return
    except FloodWaitErrorNormalized as exc:
        await reply_target.answer(str(exc))
        await manager.end_flow(user_id)
        await state.clear()
        return
    except ClientAdapterError:
        await reply_target.answer("Something went wrong verifying the code. Please /cancel and try again.")
        await manager.end_flow(user_id)
        await state.clear()
        return
    except Exception as exc:
        logger.error("Unexpected error during sign-in: %s", redact_exception(exc))
        await reply_target.answer("An unexpected error occurred. Please /cancel and try again.")
        await manager.end_flow(user_id)
        await state.clear()
        return

    await _finalize(user_id, chat_id, state, manager, reply_target)


@router.message(SessionFlow.entering_password)
async def receive_password(
    message: Message, state: FSMContext, manager: SessionManager, settings: Settings
) -> None:
    flow = manager.get_flow(message.from_user.id)
    if flow is None or flow.adapter is None:
        await message.answer(ALREADY_ACTIVE_TEXT)
        return
    try:
        password = validate_password(message.text or "")
    except ValidationError as exc:
        await message.answer(str(exc))
        return
    finally:
        await _delete_silently(message)

    try:
        await flow.adapter.sign_in_with_password(password)
    except InvalidPasswordError:
        flow.auth_attempts += 1
        if flow.auth_attempts >= settings.max_auth_attempts:
            await message.answer("Too many invalid attempts. Cancelling for your security.")
            await manager.end_flow(message.from_user.id)
            await state.clear()
            return
        await message.answer("Incorrect password. Please try again.")
        return
    except FloodWaitErrorNormalized as exc:
        await message.answer(str(exc))
        await manager.end_flow(message.from_user.id)
        await state.clear()
        return
    except ClientAdapterError:
        await message.answer("Something went wrong verifying your password. Please /cancel and try again.")
        await manager.end_flow(message.from_user.id)
        await state.clear()
        return
    finally:
        password = None  # noqa: F841 - drop reference promptly

    await _finalize(message.from_user.id, message.chat.id, state, manager, message)


# ---------------------------------------------------------------------------
# Finalization
# ---------------------------------------------------------------------------

async def _finalize(user_id: int, chat_id: int, state, manager: SessionManager, reply_target) -> None:
    flow = manager.get_flow(user_id)
    if flow is None or flow.adapter is None:
        await reply_target.answer("Session expired, send /start again.")
        return

    try:
        if flow.output_type == "string":
            session_value = await flow.adapter.export_string_session()
            await reply_target.answer(
                f"✅ Your session string:\n\n<code>{_escape_html(session_value)}</code>\n\n{SESSION_STRING_WARNING}",
                protect_content=True,
            )
            session_value = None  # drop reference
        else:
            data = await flow.adapter.export_session_file_bytes()
            filename = "telethon.session" if flow.client_type == "telethon" else "pyrogram.session"
            await reply_target.answer_document(
                BufferedInputFile(data, filename=filename),
                caption=SESSION_STRING_WARNING,
                protect_content=True,
            )
            data = b""  # drop reference
    except Exception as exc:
        logger.error("Error finalizing session export: %s", redact_exception(exc))
        await reply_target.answer("Failed to generate the session. Please /cancel and try again.")
    finally:
        ctx = getattr(flow, "_temp_dir_ctx", None)
        if ctx is not None:
            try:
                ctx.__exit__(None, None, None)
            except Exception:
                pass
        await manager.end_flow(user_id)
        await state.clear()


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def _delete_silently(message: Message) -> None:
    """Best-effort deletion of the user's message containing sensitive input,
    so it doesn't linger in chat history."""
    try:
        await message.delete()
    except Exception:
        pass
