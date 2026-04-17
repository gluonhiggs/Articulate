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
