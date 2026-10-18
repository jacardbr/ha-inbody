"""Storage helpers for the silhouette image uploaded from the card editor.

Pure standard library (no Home Assistant imports) so it can be unit tested.
Only one image is kept: a new upload replaces the previous one.
"""

from __future__ import annotations

from pathlib import Path
import re
import uuid

MAX_BYTES = 5 * 1024 * 1024
SUBDIR = "silhouettes"
_NAME_RE = re.compile(r"^silhouette-[0-9a-f]{12}\.(png|jpg|webp|gif)$")


def sniff_image(data: bytes) -> str | None:
    """Return png/jpg/webp/gif from the file's magic bytes, else None.

    SVG is deliberately not accepted: it can carry scripts, and the files are
    served from Home Assistant's own origin.
    """
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return None


def is_valid_name(name: str) -> bool:
    return bool(_NAME_RE.match(name))


def store(root: Path, data: bytes, ext: str) -> str:
    """Save the image under root/silhouettes and drop any previous one."""
    folder = root / SUBDIR
    folder.mkdir(parents=True, exist_ok=True)
    name = f"silhouette-{uuid.uuid4().hex[:12]}.{ext}"
    (folder / name).write_bytes(data)
    for old in folder.iterdir():
        if old.name != name and is_valid_name(old.name):
            old.unlink(missing_ok=True)
    return name


def delete(root: Path, name: str) -> bool:
    """Delete a stored image by name. False if the name is not one of ours."""
    if not is_valid_name(name):
        return False
    (root / SUBDIR / name).unlink(missing_ok=True)
    return True
