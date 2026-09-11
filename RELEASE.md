# Release Guide — Score Trans

Packaging + release upload are fully automated by
`.github/workflows/build-windows.yml` and `.github/workflows/build-mac.yml`.
You only push a tag — CI does the rest.

## Prerequisites

- All work merged into `main`, and `main` is green (Build Windows + Build macOS pass).
- The version you are about to release is not already tagged.

## Steps

### 1. Bump the version (two files must match)

Versions are three-segment `x.y.z` (no pre-release suffix). Update **both**:

- `desktop/package.json` → `"version": "1.0.3"`
- `desktop/latest.json`  → `"version": "1.0.3"` (optionally update `"notes"`)

```bash
git add desktop/package.json desktop/latest.json
git commit -m "release: 1.0.3"
git push origin main
```

Pushing `main` triggers Build Windows + Build macOS (validation; produces test
artifacts in the Actions run). Wait for both to pass before tagging.

### 2. Tag the release

```bash
git tag -a v1.0.3 -m "Release v1.0.3"
git push origin v1.0.3
```

The tag push triggers both workflows' tag build. The first to finish runs
`gh release create v1.0.3 ...` (creates the Release + uploads its assets); the
second finds the Release already exists and runs `gh release upload ... --clobber`
(adds its assets). No manual UI step.

### 3. Verify

Open `https://github.com/Queen405/score_trans/releases/tag/v1.0.3`. Three assets
should appear:

| File | Platform |
|---|---|
| `Score Trans Setup 1.0.3.exe` | Windows x64 |
| `Score Trans-1.0.3-arm64.dmg` | macOS arm64 |
| `Score Trans-1.0.3-arm64.zip` | macOS arm64 |

## Rules & gotchas

- **Version must be three-segment** (`1.0.3`). The in-app updater only parses
  `major.minor.patch`; pre-release tags like `1.0.3-beta` break the update check.
- **`package.json` and `latest.json` versions must be identical** — otherwise
  users see a false "new version" badge or miss a real one.
- **Push `main` before tagging.** `latest.json` is served to clients via jsDelivr,
  which mirrors the committed repo content. Tagging without pushing means clients
  fetch a stale manifest.
- **Don't put `latest.json` in `desktop/build/`** — that dir is gitignored for
  generated files; jsDelivr wouldn't see it.
- **Installers are unsigned.** Windows SmartScreen warns on first run; macOS
  requires right-click → Open. To sign later:
  - **Windows**: get a code-signing cert (SignPath Foundation is free for OSS;
    else an OV cert ~$219/yr). Add repo secrets `CSC_LINK` (PFX base64) +
    `CSC_KEY_PASSWORD` and electron-builder auto-signs. Since June 2023 new OV
    keys live on HSM, so for CI use a cloud-HSM service (SignPath / Azure Trusted
    Signing ~$10/mo).
  - **macOS**: Apple Developer ID cert ($99/yr) + notarization secrets; remove
    `CSC_IDENTITY_AUTO_DISCOVERY: 'false'` / `notarize: false` in build-mac.yml.
- **Transient upload failure on the tag build?** Re-run the failed job from the
  Actions tab — the `--clobber` flag makes asset upload idempotent.

## What each trigger does

| Trigger | Workflows | Effect |
|---|---|---|
| `pull_request` (any PR) | `ci.yml` only | lint + tests (no packaging) |
| `push` to `main` | `build-windows.yml`, `build-mac.yml` | full packaging build → Actions artifacts (14-day) |
| `push` of tag `v*` | `build-windows.yml`, `build-mac.yml` | full build + **create/upload GitHub Release** |
| `workflow_dispatch` | one chosen workflow | manual full build (artifacts only) |
