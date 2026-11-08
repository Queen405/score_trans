# Release Guide — Score Trans

## Normal release

1. Set desktop/package.json and desktop/latest.json to the same x.y.z version
   and prepare the manifest's release notes. The GitHub release body is generated
   by tools/release.py from the commits between the previous version tag and the
   new tag (grouped What's Changed); the manifest notes are used as the lead
   paragraph. Repositories without pull requests still get a full commit list.
2. Push or merge to the default branch (main). Package and release runs quality
   checks, Windows x64 and macOS arm64 packaging, and installed-app smoke tests.
3. After all three jobs pass, the serialized delivery job validates both installers
   and creates an annotated vX.Y.Z tag at that build's exact commit.
4. The same run publishes the complete GitHub Release, uploads both installers to
   COS, verifies their public bytes, and promotes the update manifest.
   No separate tag push or manual manifest upload is needed.

Manual Package and release with mode **build** on the default branch does the same.
Feature-branch manual builds remain build-only. Manually pushed vX.Y.Z tags still
support the existing build-and-publish path. Platform-only workflows never publish.
The automatic tag uses GITHUB_TOKEN; delivery consumes this run's artifacts directly
instead of relying on that tag to start another workflow.

The delivery sequence is: validate inputs/configuration → create or verify tag →
complete and verify GitHub draft snapshot → publish GitHub archive → upload and
verify both public COS installers → promote COS latest.json → update GitHub Latest.
A GitHub archive can become public before COS delivery succeeds; interrupted
COS delivery is resumable using the same immutable GitHub snapshot.

An existing version tag is reused only when it resolves to this exact build commit.
If a later commit retains an already-tagged version, automatic publication fails
with a version-conflict error. Bump the version for a new build; never move an
existing tag or replace public installer bytes. A legacy COS manifest with the same
version but different contents also requires a new version, not an overwrite.

GitHub and COS receive identical manifest bytes. SHA256SUMS.txt covers the
installers, manifest and release-metadata.json (version, tag, source commit).
The checksums asset is uploaded LAST and marks an immutable, complete snapshot.
GitHub may replace spaces in installer filenames with dots. Recovery maps those
known names back to the canonical filenames before checksum verification and COS
upload, preserving the website URLs. Unknown names or duplicate aliases fail.

## Recover interrupted delivery

In Actions, run **Package and release** from the repository's default branch:
choose mode **resume** and release_tag **vX.Y.Z**.

Draft lookup uses the authenticated, paginated release list and reads the selected
release by ID; the by-tag REST endpoint only returns published releases. Duplicate
drafts fail explicitly so delivery cannot select the wrong snapshot.

Recovery reuses the draft/public snapshot, verifies checksums and tag provenance,
and finishes missing stages. It does not rebuild or replace published assets.
Rerunning a failed ordinary release job uses the same recovery logic when the
snapshot is complete. An incomplete draft without SHA256SUMS.txt can be repaired
by rerunning the original default-branch or tag build.

Existing COS files are downloaded publicly and hashed. Identical files are reused;
conflicting bytes fail without overwriting them. Legacy releases without metadata
can be recovered only from their existing complete assets and valid SHA256SUMS.txt.
Missing checksums, moved tags, wrong destinations or corrupt snapshots require
investigation; do not replace public assets or move public tags.

CLI equivalents (normally executed only by CI):

- .venv/bin/python tools/release.py validate
- .venv/bin/python tools/release.py auto-publish --assets release-assets (default-branch CI only)
- .venv/bin/python tools/release.py publish --assets release-assets (tag CI)
- .venv/bin/python tools/release.py resume --tag vX.Y.Z

These paths are for the Linux delivery runner; use .venv/Scripts/python.exe on Windows.

## Update-channel rules

All release/recovery jobs share the score-trans-release concurrency group with
queue: max and cancellation disabled, including automatic tag creation. Platform
builds remain parallel.
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

## Website integration

The local website reads APP_VERSION from website/src/data/site.ts and constructs
COS URLs with installerUrl / installerUrlMac. DownloadSection.vue uses these URLs
for the homepage; ChangelogView.vue uses each historical entry's version.
With the default bucket, the object keys for 1.0.3 are:

- download/Score Trans Setup 1.0.3.exe (Windows x64)
- download/Score Trans-1.0.3-arm64.dmg (macOS Apple Silicon)

The release uploader uses these exact names, so publishing both files supplies the
website's existing download links. Spaces are URL-encoded by the URL builders.
The homepage does not fetch latest.json or check availability before displaying
links. The desktop updater reads download/latest.json; CI generates both url and
urlMac only from the validated release version and configured COS destination.

website/ is ignored by this repository and deployed separately. When publishing a
new version, update its APP_VERSION, APP_RELEASE_DATE and changelog locally, then
rebuild/deploy the website after delivery succeeds. Uploading latest.json does not
change the website's displayed version. Changing COS destination also requires
updating the website's CDN_BASE and the desktop update endpoint.

## Validation and limits

Windows: strict silent install → backend/API and packaged Electron smoke →
same-version reinstall → Electron smoke → uninstall, preserving user data.
Any installer nonzero exit or timeout fails; 7z extraction is never a substitute.

macOS: mount the final DMG, copy its app preserving metadata, and run backend and
packaged Electron smoke from the copied application. Always detach the image.

Desktop smoke checks visible Vue UI, preload/IPC, renderer-authenticated backend
rendering, and normal shutdown of Electron plus its backend. Runtime smoke also
checks SVG/PDF/MIDI and real Audiveris recognition. Smoke runs only on disposable
GitHub-hosted runners. Diagnostic artifacts are retained for 3 days and are not
downloaded by the release job. Installer artifacts are retained for 1 day — they
are only handed to the release job within the same run, then published to GitHub
Release and COS as the durable copies.

Unsigned Windows x64 and unnotarized macOS arm64 remain the supported targets.
Gatekeeper/SmartScreen, interactive installation and cross-version migrations
still require manual QA; CI startup does not certify those experiences.

Before production rollout, run both platform builds from a feature branch and
exercise retries/older-version delivery in an isolated repository/prefix. Never
move an existing production tag or roll back latest.json to test recovery.
