# CurseForge No-Key Auto Resolution Design

## Goal

Implement a no-key CurseForge artifact resolution chain that can turn common CurseForge exported modpack ZIP files into server directories with downloaded mod jars, without requiring each user to apply for a CurseForge API key.

The initial acceptance target is the two local CurseForge samples already analyzed by the project:

- `RLCraft 1.12.2 - Release v2.9.3.zip`
- `Into the backrooms- Found Footage (horror)-2.0.3.zip`

For these samples, Pack2Serve should attempt automatic artifact resolution for every `projectID/fileID` entry and reduce `manual_actions` to zero when configured/default no-key providers can resolve all files.

## Scope

This spec covers only CurseForge artifact resolution and reporting. It does not cover the broader web panel hosting UI, process manager, server compatibility fixer, or official CurseForge API-key provider.

The feature must preserve the existing project behavior:

- Modrinth direct downloads continue to work through `downloads[]`.
- CurseForge unresolved files still become explicit `missing-curseforge-artifact` manual actions.
- Existing `--curseforge-mirror` template support remains available.
- Generated reports remain UTF-8 JSON.

## Constraints

- No user-provided CurseForge API key is required for the default path.
- Providers are pluggable and ordered.
- Third-party mirror/provider failures must never be silent.
- Downloaded artifacts are cached before being copied into `mods/`.
- Cache metadata records provider name, `projectID`, `fileID`, file name, source URL when available, file size when known, and timestamp.
- The CLI must expose a way to disable bundled default no-key providers for repeatable testing and conservative deployments.
- The implementation must not claim guaranteed 100% CurseForge compatibility. It should report actual provider coverage.

## Data Sources

CurseForge exported ZIP files contain:

- `manifest.json`, including `minecraft.version`, loader IDs, and `files[]` with `projectID`, `fileID`, and `required`.
- `modlist.html`, usually containing links like `https://www.curseforge.com/minecraft/mc-mods/<slug>`.
- `overrides/`, containing configs, scripts, resources, worlds, and sometimes third-party jars.

The manifest alone is enough for API-style providers such as `curse.tools`. Curse Maven style providers also need a project slug, which can usually be recovered from `modlist.html`.

## Provider Chain

Pack2Serve will add a provider chain specifically for CurseForge files:

1. Local cache lookup by `curseforge:<projectID>:<fileID>`.
2. API-compatible no-key provider, initially `curse.tools`.
3. Curse Maven style provider using slug from `modlist.html`.
4. User-configured template providers from `--curseforge-mirror`.
5. Manual action fallback.

The provider chain stops on the first successful artifact. A successful artifact means:

- A file name is known.
- The file is downloaded or found in cache.
- The artifact exists on disk and has non-zero size.
- If hash or size metadata is available, it validates.

## Interfaces

Add a `CurseForgeFileContext` model:

```python
@dataclass(frozen=True)
class CurseForgeFileContext:
    project_id: int
    file_id: int
    required: bool
    slug: str | None = None
    display_name: str | None = None
```

Add a `ResolvedCurseForgeArtifact` model:

```python
@dataclass(frozen=True)
class ResolvedCurseForgeArtifact:
    provider: str
    project_id: int
    file_id: int
    file_name: str
    download_url: str
    size: int | None = None
    hashes: dict[str, str] = field(default_factory=dict)
```

Add a provider protocol:

```python
class CurseForgeArtifactProvider(Protocol):
    name: str

    def resolve(self, context: CurseForgeFileContext) -> ResolvedCurseForgeArtifact | None:
        ...
```

The downloader will own the actual file transfer and cache write. Providers only resolve metadata and download URL.

## Slug Recovery

`parser.py` should parse `modlist.html` for CurseForge project links and build a slug list in order. CurseForge modpack manifests list `files[]` in the same order as `modlist.html` in the local samples, so Pack2Serve will attach slugs by index when counts match or when a link can be associated by future metadata.

If slug recovery fails, API-compatible providers still run; Curse Maven style providers are skipped for that file.

The build report should include recovered slug/display name where available.

## Cache Layout

CurseForge artifacts are cached under:

```text
data/cache/curseforge/<projectID>/<fileID>/<fileName>
```

Metadata is written beside the artifact as:

```json
{
  "provider": "curse-tools",
  "projectID": 561885,
  "fileID": 6290217,
  "fileName": "example.jar",
  "downloadUrl": "https://...",
  "size": 12345,
  "hashes": {},
  "downloadedAt": "2026-07-19T00:00:00Z"
}
```

## CLI Behavior

Default behavior:

```powershell
python -m pack2serve.cli build pack.zip --target data/servers/example --download
```

When `pack.zip` is CurseForge format and `--download` is enabled, bundled no-key providers are enabled by default.

Disable bundled providers:

```powershell
python -m pack2serve.cli build pack.zip --target data/servers/example --download --no-default-curseforge-providers
```

Additional mirrors still append to the chain:

```powershell
python -m pack2serve.cli build pack.zip --target data/servers/example --download --curseforge-mirror "https://mirror.example/{projectID}/{fileID}/{fileName}"
```

## Reporting

`build-report.json` should retain `manual_actions`, but add resolver evidence for CurseForge builds:

```json
{
  "curseforgeResolution": {
    "resolved": 36,
    "unresolved": 0,
    "providers": {
      "cache": 10,
      "curse-tools": 20,
      "curse-maven": 6
    }
  }
}
```

The panel summary should expose:

- `resolvedRemoteFiles`
- `manualActions`
- `providersUsed`

## Error Handling

Provider errors are collected per file and included in the manual action `details.providerErrors` list.

If a provider returns a URL but download fails, the next provider is tried.

If all providers fail, the manual action message remains explicit:

```text
This CurseForge file could not be resolved from configured no-key providers. Configure another mirror or upload the jar manually.
```

## Testing

Use TDD for every behavior change.

Required test coverage:

- Parses `modlist.html` slugs and attaches them to CurseForge `RemoteFile` entries.
- Resolves a CurseForge file through an API-compatible provider response.
- Resolves a CurseForge file through a Curse Maven provider when slug is available.
- Falls through to user template provider after bundled providers fail.
- Writes cache metadata with CurseForge project/file identity.
- Produces zero manual actions when all required CurseForge files resolve.
- Produces manual actions with provider error details when no provider resolves.
- CLI `--no-default-curseforge-providers` disables bundled providers.
- Panel import uses default no-key providers when `download=true`.

## Acceptance Criteria

- Unit tests pass.
- Existing Modrinth tests pass unchanged.
- Existing CurseForge template mirror behavior remains compatible.
- `Into the Backrooms` is rebuilt with `--download`; expected result is `manualActions: 0` if current providers can resolve every file.
- `RLCraft` is rebuilt with `--download`; expected result is `manualActions: 0` if current providers can resolve every file.
- If a third-party provider is unavailable at test time, the report must show exact unresolved counts and provider errors instead of pretending completion.

## Known Risks

- Third-party no-key providers may rate-limit, disappear, or omit files.
- Some CurseForge authors disable third-party distribution.
- `modlist.html` order matching is an empirical rule, not a formal CurseForge guarantee.
- Public hosting of third-party mirror downloads may require legal review before production use.

## Out of Scope Follow-Ups

- Official CurseForge API-key provider.
- Browser upload of unresolved jars.
- Server-side mod compatibility fixer.
- Process manager and panel-hosted runtime controls.
