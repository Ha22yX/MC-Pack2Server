from __future__ import annotations

import re
import shutil
import subprocess

from pack2serve.models import JavaPlan


def required_java_major(minecraft_version: str) -> int:
    parts = _version_parts(minecraft_version)
    minor = parts[1] if len(parts) > 1 else 0
    patch = parts[2] if len(parts) > 2 else 0

    if minor <= 16:
        return 8
    if minor == 17:
        return 16
    if minor == 20 and patch <= 4:
        return 17
    if minor <= 20:
        return 17
    return 21


def plan_java(minecraft_version: str) -> JavaPlan:
    required = required_java_major(minecraft_version)
    java_path = shutil.which("java")
    detected = _detect_java_major(java_path) if java_path else None
    status = java_status(required, detected)
    return JavaPlan(
        required_major=required,
        detected_major=detected,
        detected_path=java_path,
        status=status,
    )


def java_status(required_major: int, detected_major: int | None) -> str:
    if detected_major is None:
        return "missing"
    if detected_major < required_major:
        return "too-old"
    if detected_major > required_major:
        return "newer-than-recommended"
    return "ok"


def _version_parts(version: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", version)[:3])


def _detect_java_major(java_path: str | None) -> int | None:
    if not java_path:
        return None
    try:
        proc = subprocess.run(
            [java_path, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = proc.stderr + proc.stdout
    match = re.search(r'version "([^"]+)"', text)
    if not match:
        return None
    version = match.group(1)
    if version.startswith("1."):
        return int(version.split(".")[1])
    return int(version.split(".")[0])
