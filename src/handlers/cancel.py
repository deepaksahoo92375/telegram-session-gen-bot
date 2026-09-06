"""/cancel command: securely stop and wipe any in-progress flow."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.constants import CANCELLED_TEXT
from src.flow.session_manager import SessionManager

router = Router(name="cancel")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, manager: SessionManager) -> None:
    await manager.end_flow(message.from_user.id)
    await state.clear()
    await message.answer(CANCELLED_TEXT)
