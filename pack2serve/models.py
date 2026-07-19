from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class ModpackFormat(StrEnum):
    MODRINTH = "modrinth"
    CURSEFORGE = "curseforge"


@dataclass(frozen=True)
class LoaderInfo:
    name: str
    version: str


@dataclass(frozen=True)
class RemoteFile:
    provider: str
    target_path: str
    downloads: list[str] = field(default_factory=list)
    hashes: dict[str, str] = field(default_factory=dict)
    size: int | None = None
    env: dict[str, str] = field(default_factory=dict)
    project_id: int | None = None
    file_id: int | None = None
    required: bool = True
    slug: str | None = None
    display_name: str | None = None


@dataclass(frozen=True)
class ModpackInfo:
    source_path: Path
    format: ModpackFormat
    name: str
    version: str
    minecraft_version: str
    loader: LoaderInfo
    override_root: str
    remote_files: list[RemoteFile]


@dataclass(frozen=True)
class JavaPlan:
    required_major: int
    detected_major: int | None
    detected_path: str | None
    status: str


@dataclass(frozen=True)
class CopiedOverride:
    source: str
    destination: str
    classification: str
    size: int


@dataclass(frozen=True)
class ManualAction:
    type: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CurseForgeResolutionSummary:
    resolved: int = 0
    unresolved: int = 0
    providers: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class BuildReport:
    pack: ModpackInfo
    target_dir: Path
    java: JavaPlan
    downloads: list[RemoteFile]
    copied_overrides: list[CopiedOverride]
    manual_actions: list[ManualAction]
    curseforge_resolution: CurseForgeResolutionSummary | None = None

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["pack"]["source_path"] = str(self.pack.source_path)
        data["target_dir"] = str(self.target_dir)
        return data
