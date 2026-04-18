# TODOS

Deferred work tracked from planning and review sessions.

---

## P2 — Wire auto-updates in Electron desktop app

**What:** Add `autoUpdater.checkForUpdatesAndNotify()` to `electron/main.ts` and configure `electron-builder` to publish `latest.yml` update manifests alongside release assets.

**Why:** `electron-updater` (v6.3.4) is already installed in `electron/package.json` but never called. Users currently have to manually download new versions from GitHub Releases — they get no in-app notification when updates are available.

**Pros:** Users stay on latest version automatically; no manual re-download needed; standard for desktop apps.

**Cons:** Requires a publish target configured in `electron/package.json` (GitHub token in CI secrets); needs UI to show update progress or at-least-notify toast.

**Context:** Auto-updates need a public GitHub release URL as the update feed. The `release.yml` workflow already creates GitHub Releases — just needs `electron-builder --publish always` and `autoUpdater.setFeedURL(...)` wired into `electron/main.ts` main window lifecycle. Consider showing a non-intrusive banner rather than forcing restart.

**Effort:** M (human: ~1 day) → with CC: ~30 min  
**Priority:** P2 — not blocking v1.0 but users won't get updates silently until this ships.  
**Depends on:** First public GitHub Release (tag v1.0.0) must exist before testing.

---

## P1 — Download-page UX for 5-artifact release (CPU vs GPU variant)

**What:** GitHub Release page now lists 5 installers per tag: `Articulate-{windows,linux}-{cpu,gpu}-X.Y.Z.{exe,AppImage}` plus `Articulate-macos-cpu-X.Y.Z.dmg`. Users have to pick one. Add copy + routing that makes the choice obvious.

**Why:** Capability is cleanly split at the bundle layer (`ARTICULATE_BUILD_GPU` in `backend.spec`, `local-transcription-gpu` dep-group in `pyproject.toml`), but zero user-facing guidance exists on which to pick. Wrong choice is recoverable (GPU variant on CPU box falls through `_force_cpu_fallback` at `backend/services/transcription.py:98-138`, CPU variant on GPU box just runs slower), but the first impression is "which file do I want?".

**Scope:**
- Release notes template (via `gh release create --notes-file` in `release.yml`): short table mapping OS + hardware → asset, with plain-English guidance.
- Labels on the release: "CPU (smaller, ~510 MB, runs on any machine)" / "GPU (~1.7 GB, requires NVIDIA GPU, ~10× faster)".
- Fallback hint: "Not sure? Pick CPU — you can reinstall later if you upgrade hardware."
- Optional: a static `docs/install.md` linked from README so the download experience isn't trapped in GitHub's UI.

**Effort:** S (human: ~1 hour) → with CC: ~15 min  
**Priority:** P1 — ships with first split-variant tag. Users cannot complete install without making this choice.  
**Depends on:** First split-variant release (v0.1.5 or later).
