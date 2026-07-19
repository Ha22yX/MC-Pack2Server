# ADR 0001: CurseForge No-Key Mirror Strategy

## Status

Accepted for MVP planning.

## Context

Pack2Serve needs to import CurseForge exported modpack ZIP files. These packs usually contain:

- `manifest.json`
- `modlist.html`
- an `overrides/` directory

The `manifest.json` file lists mods with `projectID` and `fileID`, but it does not include all jar files. Official CurseForge resolution normally requires the CurseForge Core API and an API key. The project direction for the MVP is to avoid requiring any user-provided CurseForge API key and use mirror-based resolution instead.

This decision is mainly about user experience: users should be able to import common CurseForge ZIP modpacks without first applying for an API key.

## Decision

Pack2Serve will implement CurseForge ZIP resolution through a provider-based artifact resolver. The default MVP provider chain will be mirror-first and no-key:

1. Parse CurseForge `manifest.json`.
2. Extract each required `projectID` and `fileID`.
3. Resolve file metadata and artifacts through configured mirror providers.
4. Download files into a local content-addressed cache.
5. Copy cached artifacts into the generated server project's `mods/` directory.
6. Merge the modpack `overrides/` directory.
7. Report unresolved files for manual upload.

The implementation must not hard-code one mirror as the only path. It should support multiple providers in order:

```text
MirrorProvider[]
  -> LocalArtifactCache
  -> ManualUploadQueue
```

Official CurseForge API support remains an optional future provider, not an MVP requirement.

## Provider Interface

Each CurseForge artifact provider should implement this logical contract:

```ts
type CurseForgeManifestFile = {
  projectID: number;
  fileID: number;
  required: boolean;
};

type ResolvedArtifact = {
  provider: string;
  projectID: number;
  fileID: number;
  fileName: string;
  downloadUrl: string;
  size?: number;
  hashes?: Array<{ algo: string; value: string }>;
};

interface CurseForgeArtifactProvider {
  name: string;
  resolve(file: CurseForgeManifestFile): Promise<ResolvedArtifact | null>;
  download(artifact: ResolvedArtifact, destination: string): Promise<void>;
}
```

## Cache Strategy

Every resolved file must be cached before it is copied into a generated server:

```text
data/cache/curseforge/{projectID}/{fileID}/{fileName}
```

Cache keys:

```text
curseforge:{projectID}:{fileID}
```

The cache should store a small metadata file next to the artifact:

```json
{
  "provider": "mirror-name",
  "projectID": 0,
  "fileID": 0,
  "fileName": "example.jar",
  "size": 0,
  "hashes": [],
  "downloadedAt": "2026-07-19T00:00:00Z"
}
```

## Failure Behavior

Mirror resolution is not guaranteed. If all providers fail for a required file, Pack2Serve must not silently skip it.

It should create a manual action item:

```json
{
  "type": "missing-curseforge-artifact",
  "projectID": 0,
  "fileID": 0,
  "required": true,
  "message": "This CurseForge file could not be resolved from configured mirrors. Upload the jar manually to continue."
}
```

The web panel should show these items in the import wizard and allow manual jar upload.

## Risks

- Mirror coverage may be incomplete.
- Mirror URLs or APIs may change without notice.
- Some files may be unavailable because of author distribution settings.
- Download metadata may be weaker than the official API.
- Public mirrors may have rate limits or regional availability issues.
- Depending on third-party mirrors can create legal or compliance questions for public hosting.

## Mitigations

- Keep providers pluggable.
- Add local caching from day one.
- Record provider source in build reports.
- Support manual upload for missing files.
- Avoid promising 100% CurseForge compatibility in no-key mode.
- Allow a future official CurseForge API provider to be added without changing the server builder.

## Product Copy

The UI should describe this mode honestly:

```text
CurseForge no-key mode uses configured mirror sources. Some files may require manual upload if mirrors cannot resolve them.
```

It should not say:

```text
Full CurseForge automatic download is guaranteed without an API key.
```

## Consequences

This keeps the MVP easy to use, but makes the resolver layer more important. The project should treat mirror resolution as best-effort and always produce a clear build report.
