from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from pack2serve.models import LoaderInfo, ModpackFormat, ModpackInfo, RemoteFile
from pack2serve.zip_utils import require_safe_zip


def parse_modpack(path: str | Path) -> ModpackInfo:
    source = Path(path)
    with zipfile.ZipFile(source) as archive:
        require_safe_zip(archive)
        names = set(archive.namelist())
        if "modrinth.index.json" in names:
            return _parse_modrinth(source, archive)
        if "manifest.json" in names:
            return _parse_curseforge(source, archive)
    raise ValueError(f"Unsupported modpack format: {source}")


def _parse_modrinth(source: Path, archive: zipfile.ZipFile) -> ModpackInfo:
    index = _read_json(archive, "modrinth.index.json")
    deps = index.get("dependencies", {})
    loader = _loader_from_modrinth_dependencies(deps)
    remote_files = [
        RemoteFile(
            provider="modrinth",
            target_path=file.get("path", ""),
            downloads=list(file.get("downloads", [])),
            hashes=dict(file.get("hashes", {})),
            size=file.get("fileSize"),
            env=dict(file.get("env", {})),
        )
        for file in index.get("files", [])
    ]
    return ModpackInfo(
        source_path=source,
        format=ModpackFormat.MODRINTH,
        name=index.get("name") or source.stem,
        version=index.get("versionId") or "",
        minecraft_version=deps.get("minecraft", ""),
        loader=loader,
        override_root="overrides",
        remote_files=remote_files,
    )


def _parse_curseforge(source: Path, archive: zipfile.ZipFile) -> ModpackInfo:
    manifest = _read_json(archive, "manifest.json")
    minecraft = manifest.get("minecraft", {})
    loader = _loader_from_curseforge_modloaders(minecraft.get("modLoaders", []))
    modlist_entries = _read_curseforge_modlist(archive)
    remote_files = [
        RemoteFile(
            provider="curseforge",
            target_path="mods",
            project_id=file.get("projectID"),
            file_id=file.get("fileID"),
            required=bool(file.get("required", True)),
            slug=modlist_entries[index][0] if index < len(modlist_entries) else None,
            display_name=modlist_entries[index][1] if index < len(modlist_entries) else None,
        )
        for index, file in enumerate(manifest.get("files", []))
    ]
    return ModpackInfo(
        source_path=source,
        format=ModpackFormat.CURSEFORGE,
        name=manifest.get("name") or source.stem,
        version=manifest.get("version") or "",
        minecraft_version=minecraft.get("version", ""),
        loader=loader,
        override_root=manifest.get("overrides") or "overrides",
        remote_files=remote_files,
    )


def _read_json(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    return json.loads(archive.read(name).decode("utf-8-sig"))


def _read_curseforge_modlist(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    if "modlist.html" not in archive.namelist():
        return []
    html = archive.read("modlist.html").decode("utf-8", errors="replace")
    entries: list[tuple[str, str]] = []
    pattern = re.compile(
        r'href=["\']https?://www\.curseforge\.com/minecraft/[^/"\']+/([^/"\']+)["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    for slug, label in pattern.findall(html):
        display_name = re.sub(r"\s*\(by .*\)\s*$", "", _strip_html(label), flags=re.IGNORECASE).strip()
        entries.append((slug.strip(), display_name))
    return entries


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value).strip()


def _loader_from_modrinth_dependencies(deps: dict[str, str]) -> LoaderInfo:
    for key in ("forge", "neoforge", "fabric-loader", "quilt-loader"):
        if key in deps:
            return LoaderInfo(name=key, version=deps[key])
    return LoaderInfo(name="vanilla", version=deps.get("minecraft", ""))


def _loader_from_curseforge_modloaders(loaders: list[dict[str, Any]]) -> LoaderInfo:
    primary = next((loader for loader in loaders if loader.get("primary")), loaders[0] if loaders else {})
    raw = primary.get("id", "vanilla")
    if "-" not in raw:
        return LoaderInfo(name=raw, version="")
    name, version = raw.split("-", 1)
    return LoaderInfo(name=name, version=version)
