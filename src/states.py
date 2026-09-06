"""aiogram FSM states for the session-generation flow."""
from aiogram.fsm.state import State, StatesGroup


class SessionFlow(StatesGroup):
    """States for the multi-step, single-user session generation flow."""

    awaiting_consent = State()
    choosing_client = State()
    choosing_output = State()
    entering_api_id = State()
    entering_api_hash = State()
    entering_phone = State()
    entering_code = State()
    entering_password = State()
    finalizing = State()
