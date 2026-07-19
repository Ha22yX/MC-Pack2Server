from __future__ import annotations

import shutil
import zipfile
from pathlib import Path, PurePosixPath


def require_safe_zip(archive: zipfile.ZipFile) -> None:
    unsafe = [name for name in archive.namelist() if not is_safe_zip_path(name)]
    if unsafe:
        raise ValueError(f"Unsafe ZIP paths: {unsafe[:5]}")


def is_safe_zip_path(name: str) -> bool:
    path = PurePosixPath(name)
    return not (
        name.startswith("/")
        or "\\" in name
        or ".." in path.parts
        or (len(name) > 1 and name[1] == ":")
    )


def copy_member(archive: zipfile.ZipFile, member: zipfile.ZipInfo, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with archive.open(member) as src, destination.open("wb") as dst:
        shutil.copyfileobj(src, dst)

