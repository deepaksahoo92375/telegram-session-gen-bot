"""/start command: privacy warning + explicit consent gate."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.constants import CONSENT_TEXT
from src.states import SessionFlow

router = Router(name="start")


def _consent_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ I consent, continue", callback_data="consent:yes"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="consent:no"),
            ]
        ]
    )


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(SessionFlow.awaiting_consent)
    await message.answer(
        CONSENT_TEXT,
        reply_markup=_consent_keyboard(),
        disable_web_page_preview=True,
        protect_content=True,
    )


@router.callback_query(F.data == "consent:no", SessionFlow.awaiting_consent)
async def consent_declined(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Understood — no data will be processed. Send /start to begin again.")
    await callback.answer()
