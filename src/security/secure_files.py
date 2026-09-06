"""Secure temporary file/directory helpers.

All temp paths are created with restrictive permissions (0600 for files,
0700 for directories) and are guaranteed to be removed via context managers,
even on error.
"""
from __future__ import annotations

import os
import secrets
import shutil
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def ensure_secure_root(root: str) -> Path:
    """Create the secure temp root directory with 0700 permissions if needed."""
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, stat.S_IRWXU)  # 0700, owner-only
    return path


@contextmanager
def secure_temp_dir(root: str, prefix: str = "sess_") -> Iterator[Path]:
    """Create a per-flow secure temp directory, guaranteed to be wiped on exit."""
    ensure_secure_root(root)
    unique = f"{prefix}{secrets.token_hex(8)}"
    directory = Path(root) / unique
    directory.mkdir(mode=stat.S_IRWXU, exist_ok=False)
    os.chmod(directory, stat.S_IRWXU)
    try:
        yield directory
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def write_secure_file(path: Path, data: bytes) -> Path:
    """Write bytes to ``path`` with 0600 permissions, replacing any existing file."""
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    return path


def shred_file(path: Path, passes: int = 1) -> None:
    """Best-effort overwrite-then-delete of a file.

    True forensic wiping cannot be guaranteed on all filesystems (journaling,
    SSD wear-levelling, snapshots), so this is defense-in-depth, not a
    guarantee -- the primary control is never persisting secrets to disk in
    the first place except transiently within a secure_temp_dir().
    """
    try:
        if path.exists() and path.is_file():
            size = path.stat().st_size
            with open(path, "r+b") as fh:
                for _ in range(passes):
                    fh.seek(0)
                    fh.write(secrets.token_bytes(size))
                    fh.flush()
                    os.fsync(fh.fileno())
    except OSError:
        pass
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
