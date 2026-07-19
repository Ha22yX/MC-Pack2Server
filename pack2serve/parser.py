from __future__ import annotations

import json
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
    remote_files = [
        RemoteFile(
            provider="curseforge",
            target_path="mods",
            project_id=file.get("projectID"),
            file_id=file.get("fileID"),
            required=bool(file.get("required", True)),
        )
        for file in manifest.get("files", [])
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

