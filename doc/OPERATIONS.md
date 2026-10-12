# Documentation operations

The source is `doc/`; hardware remains in `panels/`. The prepared destination is
https://zudo-blanks.zudolab.dev with `base: "/"` and framework `/docs/` routes.
The site uses published `@takazudo/zudo-doc` / `@takazudo/zudo-doc-history-server`
6.0.2 and `@takazudo/zfb`, `@takazudo/zfb-runtime`, `@takazudo/zfb-md-wasm`, and
`@takazudo/zfb-adapter-cloudflare` 4.3.2. Cloudflare root hosting is configured
in `wrangler.jsonc` and validated without credentials. Production activation and
the old-host cutover have not been established. Documentation maintenance
authorizes no deployment, DNS change, or release.

## Local and CI verification

Use Node 22 and the package's pinned pnpm. From the repository root:

```bash
pnpm --dir doc install --frozen-lockfile
npm ci --prefix artwork-resources/pcb-art/preview-source
cd doc
pnpm check:content
pnpm check:accessories
pnpm check
pnpm check:links -- --strict-broken --strict-absolute --strict-anchors
pnpm exec zfb wind audit --project-root . --fail-on error
GEN_DOC_HISTORY=1 pnpm build
pnpm check:links -- --strict-broken --strict-absolute --strict-anchors
pnpm check:images
pnpm check:viewers
pnpm check:redirects
pnpm check:history
pnpm exec wrangler deploy --dry-run --outdir /tmp/zudo-blanks-worker-dry-run
pnpm check:worker
cd ..
python3 -m pip install -r scripts/art-order/requirements.txt
python3 artwork-resources/pcb-art/manufacturing/verify_ordered.py
```

Use the personal heavy-test guard around a local production build or browser suite
when that guard is installed. GitHub-hosted CI uses an isolated runner and a job
timeout. The documentation workflow tests a pull request's merge result against
its target branch, reruns when that pull request is edited (including a base
change), and also runs on `main` pushes. It records head/base/tested revisions,
fetches full Git history, and does not need Cloudflare or deployment credentials.
Leave history-skip variables unset. `GEN_DOC_HISTORY=1` includes history JSON in
local built reviews. The independent manufacturing workflow retains its regression
suites and archive integrity guard; native fabrication generation remains an
explicit manual task.

The build enables package-owned history generation. A narrow migration helper
uses the published history API and route map to restore prior canonical paths
when Git rename detection follows duplicate overlays or misses edited moves.
It supplies supported chrome metadata before rendering and reconciles history
JSON afterward; `check:history` verifies both against full Git history.

Published zudo-doc 6.0.2 still bounds default first/last metadata queries to the
configured content roots. A page that arrives from outside those roots can receive
the move date as its creation date, while the revision-history API retains the
earlier revisions. The [upstream reproduction](https://github.com/zudolab/zudo-doc/issues/2517#issuecomment-6111082841)
tracks that metadata defect; closing the older issue did not change this
pre-build behavior between 6.0.0 and 6.0.2. `scripts/reconcile-history.mjs` uses
`collectContentFiles` / `getDocHistoryAsync` and `data/route-migration.json` to
restore original creation metadata before rendering and canonical revisions
afterward. `check:history` verifies both against full Git history. The current
coverage includes 22 moved destinations and 41 prior-path revisions; those counts
are a baseline, and later legitimate revisions stay in the same continuity.
Keep the helper until a published fix passes the same original-date and
History/Compare checks. No manufacturing data depends on this metadata.

`check:accessories` walks `_3dp/` separately from the 19 panel families. Supported
printable/model extensions are `.3mf`, `.stl`, `.step`, `.stp`, and `.fcstd`.
Each such file needs an entry in the `models` map in `scripts/stage_viewers.mjs`
or a non-empty exclusion reason. The mapped M3 spacer project is copied unchanged
to `/assets/models/blank-module-spacer-m3.3mf`; the check compares those bytes and
the output manifest with the repository original. An unclassified supported file
fails with its source path.

`check:content` covers dynamic inventory and generated-output drift without KiCad,
Pillow or macOS `sips`. Normal builds reuse committed images. Native board image
regeneration is a separate, intentional maintenance task; never refresh frozen
geometry or retained order files to make a docs check pass.

For interactive review, run `pnpm exec wrangler dev --local` from `doc/` after a
build. `check:browser` launches the preview toolchain's Linux Chromium. On a host
that cannot execute that binary, set `BROWSER_EXECUTABLE` to a native Chromium and
leave it unset in CI. Review desktop/mobile and light/dark pages; search; History/Compare;
transitions; sidebar focus, broaden and restore; direct reloads; query/hash links;
all viewer controls including Kumiko wide/standard and Strip Mine pattern 5,
Strata/blobs; representative redirects; mechanical downloads; and the M3 spacer
project download. Confirm a missing
page has HTTP 404 and a styled error page. Automated HTTP checks do not replace
these browser interactions.

## Worker output contract

Wrangler uses `dist/_worker.js`, assets in `dist/`, binding `ASSETS`, and
`nodejs_compat`. Unknown static paths use `404-page`, never SPA fallback. Keep the
adapter-generated `dist/.assetsignore` intact: Worker, inner server bundles, and
Wasm modules must not become downloadable static assets. Do not overwrite it with
a shortened handwritten list. Check asset sizes against current Workers limits
before activation. Curated models, committed previews, and two canonical viewer
bundles are web assets; the completed order archive remains an ordinary Git
repository download. No bulk archive copy or extra storage service is required.

## Route compatibility and the old host

The committed route map and redirect generator are the source of truth for old
page, raw-file, and viewer mappings. New-host compatibility maps old section and
viewer URLs to their replacements, preserving selection queries and browser
fragments. The five destinations are `/docs/panels/`, `/docs/models/`,
`/docs/manufacturing/`, `/docs/guides/`, and `/docs/overview/`.

The reviewed template is `scripts/old-host-redirect.mjs`; it retains the old
prefix so the new hostname can apply its explicit migration map.
The former host, `takazudomodular.com`, needs a **separate** authorized redirect
handler for `/pj/zblanks` and `/pj/zblanks/*`. The new Worker cannot intercept
requests addressed to that hostname. Change the hostname while retaining the
complete old pathname and query; let the new-host map select the final route. Fragments are
not sent to servers; avoid adding or replacing fragments in redirect locations
unless an explicit anchor migration requires it. Test old deep links, viewer
selection queries and browser-held hashes before switching old-host traffic.
Retiring this repository's Netlify tooling does not remove or modify that host.

## Completed integration

[PR #27](https://github.com/Takazudo/zudo-blanks/pull/27) merged the completed
four-series order archive as `fd93422741bd6f43b1ef73cfd6483dc135a53d2f` (final
head `c7643181803ea2314a54232b27a31156dc2dd9df`). [PR #28](https://github.com/Takazudo/zudo-blanks/pull/28)
merged the documentation site as `c7e988a699cc8f6eeb5c6abff840c149a7be1cdc` (final
head `90b4c2f163a385512af979026bf0a83309325407`). Both commits remain in `main`'s
history. The docs branch had started after parent commit
`f31c49d3cad0364033c18d4f91d07139ea4872f5` on `chore/completed-four-art-order`;
that stacking sequence is finished.

Archive downloads stay pinned to the original completed-order commit in that
ancestry. Their bytes must match the merged archive. Production activation
remains separate from this completed integration.

## Production activation: separate authorization required

There is deliberately no automatic deploy workflow. A future operator must first
obtain explicit deployment and hostname authorization, inspect the Cloudflare
account/zone and existing routing, and confirm the intended account and protected
`main` revision. Configure appropriately scoped credentials outside this repository.
The `production` Wrangler environment prepares the custom hostname but executing a
remote deploy would activate it; do not run that command as a validation step.

After authorization, on a clean checkout of the reviewed `main` commit, fetch and
verify `HEAD` equals `origin/main`, rerun the checks above, and inspect both the
production dry-run and generated `.assetsignore`. An explicit operator shell
sequence for that later activation is:

```bash
# Run from repository root only after separate production authorization.
set -euo pipefail
test "$(git branch --show-current)" = main
git fetch origin main
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
test -z "$(git status --porcelain)"
test "${ZUDO_BLANKS_ACTIVATE_PRODUCTION:-}" = "approved-main"
cd doc
pnpm exec wrangler deploy --env production --dry-run
# Review the dry-run before executing the separately authorized remote command:
pnpm exec wrangler deploy --env production
```

Set `ZUDO_BLANKS_ACTIVATE_PRODUCTION=approved-main` only for the explicitly
approved activation session. If adding deployment automation later, require a
manual dispatch, exact `main` ref, a protected production environment, and an
activation opt-in variable; never deploy from a pull request.
Validate production page content, real 404s, downloads, history, viewers and
redirects after activation. Record the deployed version and preceding version for
rollback. Rollback to that previously verified Worker version is another remote
operation and requires authorization; do not revert or regenerate the order archive.
