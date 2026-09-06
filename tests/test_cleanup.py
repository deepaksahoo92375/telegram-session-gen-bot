from pathlib import Path

import pytest

from src.security.cleanup import full_cleanup, wipe_dict


class DummyClient:
    def __init__(self):
        self.disconnected = False

    async def disconnect(self):
        self.disconnected = True


def test_wipe_dict_clears_all_values():
    data = {"a": 1, "b": "secret"}
    wipe_dict(data)
    assert data == {}


@pytest.mark.asyncio
async def test_full_cleanup_disconnects_client_and_wipes_state(tmp_path: Path):
    client = DummyClient()
    temp_file = tmp_path / "secret.session"
    temp_file.write_bytes(b"super-secret-bytes")
    state = {"api_hash": "abc", "phone": "+1555"}

    await full_cleanup(client=client, temp_files=[temp_file], state_data=state)

    assert client.disconnected is True
    assert not temp_file.exists()
    assert state == {}


@pytest.mark.asyncio
async def test_full_cleanup_is_safe_with_no_args():
    # Must not raise even when nothing was ever initialized (e.g. early cancel).
    await full_cleanup()
