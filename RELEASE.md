# Release Guide — Score Trans

## Normal release

1. Set desktop/package.json and desktop/latest.json to the same x.y.z version.
2. Merge to main and wait for Package and release to pass both platform builds.
3. Tag that exact commit vX.Y.Z and push the tag.
4. The release job automatically delivers both platforms to GitHub and COS.
   Do not follow it with a separate manual manifest upload.

The delivery sequence is: validate inputs/configuration → complete GitHub draft
snapshot → verify public COS installers → publish GitHub archive → promote COS
latest.json → update GitHub Latest. A GitHub archive can become public before the
update channel is promoted; interrupted delivery is resumable.

GitHub and COS receive identical manifest bytes. SHA256SUMS.txt covers the
installers, manifest and release-metadata.json (version, tag, source commit).
The checksums asset is uploaded LAST and marks an immutable, complete snapshot.

## Recover interrupted delivery

In Actions, run **Package and release** from the repository's default branch:
choose mode **resume** and release_tag **vX.Y.Z**.

Recovery reuses the draft/public snapshot, verifies checksums and tag provenance,
and finishes missing stages. It does not rebuild or replace published assets.
Rerunning a failed ordinary release job uses the same recovery logic when the
snapshot is complete. An incomplete draft without SHA256SUMS.txt can be repaired
by rerunning the normal tag build.

Existing COS files are downloaded publicly and hashed. Identical files are reused;
conflicting bytes fail without overwriting them. Legacy releases without metadata
can be recovered only from their existing complete assets and valid SHA256SUMS.txt.
Missing checksums, moved tags, wrong destinations or corrupt snapshots require
investigation; do not replace public assets or move public tags.

CLI equivalents (normally executed only by CI):

- python tools/release.py validate
- python tools/release.py publish --assets release-assets
- python tools/release.py resume --tag vX.Y.Z

## Update-channel rules

All release/recovery jobs share the score-trans-release concurrency group with
queue: max and cancellation disabled. Platform builds remain parallel.
An older version may be archived but cannot replace either Latest pointer.
Equal-version manifests must be byte-identical. A failed remote query is not an
empty channel: only an explicit 404 permits initialization.

Production manifest promotion has one writer: the serialized release workflow.
pnpm upload:cos now uploads versioned installers ONLY, without rewriting local
files or publishing latest.json. Its --dry-run mode performs no remote calls.
CI calls the upload script with explicit --phase=artifacts or --phase=promote,
--manifest and --checksums arguments. Old --no-sync / --no-cdn flags are tolerated
but no local synchronization or CDN purge is performed.

## Configuration and permissions

Repository secrets: TENCENTCLOUD_SECRET_ID and TENCENTCLOUD_SECRET_KEY.
The release job receives GH_TOKEN from github.token with contents: write.
No release credentials are passed to platform builds or PR checks.

Optional repository variables:
- COS_BUCKET: score-trans-1320022301
- COS_REGION: ap-beijing
- COS_PREFIX: download

Empty values use these defaults in both Python and Node. Changing destination
during recovery is rejected because the snapshot already contains its URLs.
The bucket must permit public installer/manifest reads. The COS identity needs
object reads/HEAD, upload/initiate/upload-part/complete/abort-multipart and
manifest writes; PutObject alone is insufficient. Incomplete multipart cleanup
never deletes completed installer objects. Keep other writers away from the
production prefix; the Actions lock cannot serialize uploads from other systems.
The additional forbid-overwrite header only provides COS-side protection when
bucket versioning is disabled.

Installed clients keep using the existing production COS endpoint. For mirrors
and isolated testing, set SCORE_TRANS_UPDATE_MANIFEST_URL explicitly.
Do not point a test workflow at the production download prefix.

## Validation and limits

Windows: strict silent install → backend/API and packaged Electron smoke →
same-version reinstall → Electron smoke → uninstall, preserving user data.
Any installer nonzero exit or timeout fails; 7z extraction is never a substitute.

macOS: mount the final DMG, copy its app preserving metadata, and run backend and
packaged Electron smoke from the copied application. Always detach the image.

Desktop smoke checks visible Vue UI, preload/IPC, renderer-authenticated backend
rendering, and normal shutdown of Electron plus its backend. Runtime smoke also
checks SVG/PDF/MIDI and real Audiveris recognition. Smoke runs only on disposable
GitHub-hosted runners. Diagnostic artifacts are retained for 14 days and are not
downloaded by the release job.

Unsigned Windows x64 and unnotarized macOS arm64 remain the supported targets.
Gatekeeper/SmartScreen, interactive installation and cross-version migrations
still require manual QA; CI startup does not certify those experiences.

Before production rollout, run both platform builds from a feature branch and
exercise retries/older-version delivery in an isolated repository/prefix. Never
move an existing production tag or roll back latest.json to test recovery.
