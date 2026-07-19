# CurseForge No-Key Auto Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a default no-key CurseForge provider chain that resolves exported modpack `projectID/fileID` entries into downloaded jar files and clear resolver evidence.

**Architecture:** Keep parsing, resolving, downloading, and building separated. `parser.py` enriches CurseForge `RemoteFile` entries with slug/display metadata from `modlist.html`; `downloader.py` owns provider resolution, cache metadata, and downloads; `builder.py`, `cli.py`, and `panel.py` wire default providers and report resolution summaries.

**Tech Stack:** Python standard library, `unittest`, existing `urllib.request` downloader, existing CLI and local panel.

## Global Constraints

- No user-provided CurseForge API key is required for default providers.
- Providers are pluggable and ordered.
- Third-party failures are recorded, not swallowed.
- Existing Modrinth behavior remains unchanged.
- Existing `--curseforge-mirror` template behavior remains compatible.
- No production code is added before a failing test.

---

### Task 1: CurseForge Manifest Slug Metadata

**Files:**
- Modify: `pack2serve/models.py`
- Modify: `pack2serve/parser.py`
- Test: `tests/test_pack2serve_core.py`

**Interfaces:**
- Produces: `RemoteFile.slug: str | None` and `RemoteFile.display_name: str | None`.
- Consumes: existing `parse_modpack(path) -> ModpackInfo`.

- [ ] **Step 1: Write failing parser test**

Add a test that builds a tiny CurseForge ZIP with `manifest.json` and `modlist.html`, then asserts the first remote file has `slug == "just-zoom"` and `display_name == "Just Zoom"`.

- [ ] **Step 2: Verify failure**

Run: `python -m unittest tests.test_pack2serve_core.Pack2ServeCoreTests.test_parse_curseforge_zip_attaches_modlist_slugs -v`

Expected: FAIL because `RemoteFile` has no `slug`.

- [ ] **Step 3: Implement metadata fields and parser**

Add optional fields to `RemoteFile`. Parse links matching `curseforge.com/minecraft/.../<slug>` from `modlist.html` and attach by index when counts match.

- [ ] **Step 4: Verify**

Run the single test, then `python -m unittest discover -s tests -v`.

### Task 2: Resolver Models and API-Compatible Provider

**Files:**
- Modify: `pack2serve/downloader.py`
- Test: `tests/test_pack2serve_core.py`

**Interfaces:**
- Produces: `CurseForgeFileContext`, `ResolvedCurseForgeArtifact`, `CurseForgeApiProvider`.
- Consumes: `RemoteFile.project_id`, `RemoteFile.file_id`, `RemoteFile.required`, `RemoteFile.slug`.

- [ ] **Step 1: Write failing provider test**

Create a local HTTP server returning `{"data": "http://host/files/example.jar"}` for `/mods/561885/files/6290217/download-url`. Assert `CurseForgeApiProvider.resolve()` returns file name `example.jar`.

- [ ] **Step 2: Verify failure**

Run the single provider test and confirm import/name failure.

- [ ] **Step 3: Implement provider**

Use `urllib.request` with `User-Agent: Pack2Serve/0.1.0`; return `None` on 404; raise `DownloadError` on malformed responses or network errors.

- [ ] **Step 4: Verify**

Run the single test, then all tests.

### Task 3: Curse Maven Provider

**Files:**
- Modify: `pack2serve/downloader.py`
- Test: `tests/test_pack2serve_core.py`

**Interfaces:**
- Produces: `CurseForgeMavenProvider.resolve(context)`.
- Consumes: `CurseForgeFileContext.slug`.

- [ ] **Step 1: Write failing provider test**

Assert a context with slug `just-zoom`, project `561885`, file `6290217` resolves to file name `just-zoom-561885-6290217.jar` and URL `https://www.cursemaven.com/curse/maven/just-zoom-561885/6290217/just-zoom-561885-6290217.jar`.

- [ ] **Step 2: Verify failure**

Run the single provider test and confirm provider missing.

- [ ] **Step 3: Implement provider**

Return `None` when slug is missing. Otherwise build the Maven URL without network probing; downloader will validate by attempting transfer.

- [ ] **Step 4: Verify**

Run the single test, then all tests.

### Task 4: CurseForge Resolver Chain and Cache Metadata

**Files:**
- Modify: `pack2serve/downloader.py`
- Modify: `pack2serve/builder.py`
- Test: `tests/test_pack2serve_core.py`

**Interfaces:**
- Produces: `CurseForgeResolver.resolve_and_cache(remote: RemoteFile) -> CachedArtifact`.
- Produces: `CurseForgeResolutionSummary`.
- Consumes: provider `resolve(context)`.

- [ ] **Step 1: Write failing chain tests**

Add tests for: first provider succeeds, failed provider falls through to second provider, all providers failing raises with provider error list, cache metadata contains `projectID`, `fileID`, `downloadUrl`, `provider`.

- [ ] **Step 2: Verify failure**

Run the new chain tests and confirm missing resolver/classes.

- [ ] **Step 3: Implement resolver**

Move CurseForge artifact downloads through the resolver. Write cache to `data/cache/curseforge/<projectID>/<fileID>/<fileName>`.

- [ ] **Step 4: Verify**

Run chain tests and all tests.

### Task 5: CLI and Panel Defaults

**Files:**
- Modify: `pack2serve/cli.py`
- Modify: `pack2serve/panel.py`
- Modify: `README.md`
- Modify: `docs/development/backend-mvp-status.md`
- Test: `tests/test_pack2serve_core.py`

**Interfaces:**
- Produces: CLI flag `--no-default-curseforge-providers`.
- Produces: `_curseforge_providers(cache_dir, templates, include_defaults=True)`.
- Panel import with `download=true` uses defaults.

- [ ] **Step 1: Write failing CLI/panel tests**

Add tests proving default provider list includes bundled providers, `--no-default-curseforge-providers` disables them, and panel import passes default providers when downloading.

- [ ] **Step 2: Verify failure**

Run the new CLI/panel tests and confirm missing flag/default provider behavior.

- [ ] **Step 3: Implement wiring**

Default chain: `CurseForgeApiProvider("curse-tools", "https://api.curse.tools/v1/cf")`, `CurseForgeMavenProvider("curse-maven", "https://www.cursemaven.com")`, then template providers.

- [ ] **Step 4: Verify**

Run all tests.

### Task 6: Real Sample Verification

**Files:**
- Modify: `docs/development/full-verification-2026-07-19.md`

**Interfaces:**
- Consumes: CLI build/install/validate commands.
- Produces: updated evidence for RLCraft and Into the Backrooms.

- [ ] **Step 1: Rebuild CurseForge samples**

Run:

```powershell
python -m pack2serve.cli build "C:\Users\Administrator\Downloads\Into the backrooms- Found Footage (horror)-2.0.3.zip" --target "data\servers\full-verification\into-the-backrooms" --download
python -m pack2serve.cli build "C:\Users\Administrator\Downloads\RLCraft 1.12.2 - Release v2.9.3.zip" --target "data\servers\full-verification\rlcraft" --download
```

- [ ] **Step 2: Inspect reports**

Read `manual_actions`, `curseforgeResolution`, and provider error counts from each build report.

- [ ] **Step 3: Run runtime steps where file resolution reaches zero manual actions**

Run loader install, Java install, EULA acceptance, and validation for packs with zero unresolved files.

- [ ] **Step 4: Update report**

Record exact outcome. If a provider is unavailable or incomplete, write the exact unresolved count and provider errors.

- [ ] **Step 5: Final verification and commit**

Run `python -m unittest discover -s tests -v`, commit, and push.
