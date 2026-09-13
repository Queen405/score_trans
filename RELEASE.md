# Release Guide — Score Trans

`.github/workflows/package.yml` is the only automatic packaging/release entry point.
It runs quality checks, calls both platform builds, then publishes a complete release.

## Release steps

1. Merge release-ready changes into `main`.
2. Update `desktop/package.json` and `desktop/latest.json` to the same `x.y.z` version.
   `latest.json` is release input (including notes); new clients do not fetch this
   working-branch file. Do not use prerelease version suffixes.
3. Push `main` and wait for **Package and release** to pass, including both builds.
4. Tag that exact commit `vX.Y.Z` and push the tag. The tag build validates all three
   versions again, runs quality checks and both platform smoke tests, then publishes.
5. Verify the public release contains:
   - `Score Trans Setup X.Y.Z.exe` (Windows x64)
   - `Score Trans-X.Y.Z-arm64.dmg` and `.zip` (macOS Apple Silicon)
   - `latest.json` (version-specific download page and release notes)
   - `SHA256SUMS.txt` (SHA-256 of installers and manifest)

The release job uploads every asset to a **draft** before making it public. A failed
build/test/upload cannot announce a partially uploaded new release. Failed draft
uploads can be rerun; an already public release cannot be overwritten by the script.
Do not move an existing public tag to different source code; publish a new version.

## Triggers

| Trigger | Result |
|---|---|
| PR or push to a development branch | Lightweight CI |
| Push to main/master | Quality + Windows/macOS packaging and smoke tests; artifacts only |
| Push v* tag | Same checks, then draft upload and publish |
| Manual Package and release | Both platforms; publishes only if the selected ref is a version tag |
| Manual Build Windows / Build mac | Selected platform only; never publishes |

Artifacts are retained for 14 days. Reusable platform workflows use the same commit
as the caller. The tag build deliberately rebuilds and retests: it never borrows an
artifact from a different commit or an unverified previous Actions run.

## Update discovery

New clients read `releases/latest/download/latest.json`, so the update becomes visible
only after a complete release is public. `SCORE_TRANS_UPDATE_MANIFEST_URL` can override
this endpoint for a mirror or local tests. GitHub access may be less reliable than a
regional mirror; connection failures remain non-blocking in the UI.

Older installed clients still use the historical jsDelivr repository manifest until
upgraded; changing this repository cannot retroactively change their updater code.

## Delivery limits

Windows installers are unsigned; macOS packages are not Developer-ID-signed or
notarized. Windows x64 and macOS arm64 are supported; Intel macOS is not built.
macOS packaging/startup is verified on its CI runner, not on a local Windows machine.
The Windows CI test covers silent installation, same-version reinstall, runtime API
smoke tests and uninstall preserving user data. Interactive wizard behavior and
cross-version migration still require release QA.
