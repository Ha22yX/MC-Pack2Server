from __future__ import annotations

import hashlib
import json
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from pack2serve.models import RemoteFile


@dataclass(frozen=True)
class CachedArtifact:
    provider: str
    key: str
    path: Path
    size: int


class ArtifactCache:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def path_for(self, provider: str, key: str, file_name: str) -> Path:
        safe_name = file_name.replace("/", "_").replace("\\", "_")
        return self.root / provider / key / safe_name

    def metadata_path_for(self, artifact_path: Path) -> Path:
        return artifact_path.with_suffix(artifact_path.suffix + ".pack2serve.json")

    def has_valid(self, path: Path, remote: RemoteFile) -> bool:
        if not path.exists():
            return False
        if remote.size is not None and path.stat().st_size != remote.size:
            return False
        return _hashes_match(path, remote.hashes)

    def remember(self, provider: str, key: str, artifact_path: Path, remote: RemoteFile) -> CachedArtifact:
        metadata = {
            "provider": provider,
            "key": key,
            "targetPath": remote.target_path,
            "size": artifact_path.stat().st_size,
            "hashes": remote.hashes,
        }
        self.metadata_path_for(artifact_path).write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return CachedArtifact(
            provider=provider,
            key=key,
            path=artifact_path,
            size=artifact_path.stat().st_size,
        )


class ModrinthDirectProvider:
    name = "modrinth-direct"

    def __init__(self, cache: ArtifactCache):
        self.cache = cache

    def resolve_and_cache(self, remote: RemoteFile) -> CachedArtifact:
        if not remote.downloads:
            raise DownloadError(f"Modrinth file has no download URL: {remote.target_path}")
        file_name = Path(remote.target_path).name
        key = _cache_key(remote)
        destination = self.cache.path_for(self.name, key, file_name)
        if self.cache.has_valid(destination, remote):
            return self.cache.remember(self.name, key, destination, remote)

        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_path = destination.with_suffix(destination.suffix + ".tmp")
        _download(remote.downloads[0], temp_path)
        if remote.size is not None and temp_path.stat().st_size != remote.size:
            temp_path.unlink(missing_ok=True)
            raise DownloadError(
                f"Downloaded size mismatch for {remote.target_path}: "
                f"expected {remote.size}, got {temp_path.stat().st_size}"
            )
        if not _hashes_match(temp_path, remote.hashes):
            temp_path.unlink(missing_ok=True)
            raise DownloadError(f"Downloaded hash mismatch for {remote.target_path}")
        temp_path.replace(destination)
        return self.cache.remember(self.name, key, destination, remote)


class CurseForgeTemplateMirrorProvider:
    def __init__(
        self,
        cache: ArtifactCache,
        name: str,
        url_template: str,
        file_name_template: str = "{projectID}-{fileID}.jar",
    ):
        self.cache = cache
        self.name = name
        self.url_template = url_template
        self.file_name_template = file_name_template

    def resolve_and_cache(self, remote: RemoteFile) -> CachedArtifact:
        if remote.project_id is None or remote.file_id is None:
            raise DownloadError("CurseForge mirror provider requires projectID and fileID")
        values = {
            "projectID": remote.project_id,
            "fileID": remote.file_id,
            "project_id": remote.project_id,
            "file_id": remote.file_id,
        }
        url = self.url_template.replace("%7B", "{").replace("%7D", "}").format(**values)
        file_name = self.file_name_template.format(**values)
        key = f"{remote.project_id}-{remote.file_id}"
        destination = self.cache.path_for(self.name, key, file_name)
        if destination.exists():
            return self.cache.remember(self.name, key, destination, remote)

        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_path = destination.with_suffix(destination.suffix + ".tmp")
        _download(url, temp_path)
        temp_path.replace(destination)
        return self.cache.remember(self.name, key, destination, remote)


class DownloadError(RuntimeError):
    pass


def copy_cached_artifact(artifact: CachedArtifact, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(artifact.path, target)


def _cache_key(remote: RemoteFile) -> str:
    if remote.hashes:
        algo, value = sorted(remote.hashes.items())[0]
        return f"{algo}-{value}"
    parsed = urlparse(remote.downloads[0])
    return hashlib.sha256(f"{remote.target_path}:{parsed.geturl()}".encode("utf-8")).hexdigest()


def _download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Pack2Serve/0.1.0"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output)
    except (urllib.error.URLError, OSError) as exc:
        destination.unlink(missing_ok=True)
        raise DownloadError(f"Failed to download {url}: {exc}") from exc


def _hashes_match(path: Path, hashes: dict[str, str]) -> bool:
    for algo, expected in hashes.items():
        if algo.lower() not in {"sha1", "sha512"}:
            continue
        digest = hashlib.new(algo.lower())
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest().lower() != expected.lower():
            return False
    return True
