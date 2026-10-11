# Documentation operations

The source is `doc/`; hardware remains in `panels/`. The prepared destination is
https://zudo-blanks.zudolab.dev with `base: "/"` and framework `/docs/` routes.
Configuration readiness does not mean the production hostname is active.
This migration authorizes no deployment, DNS change, release, or merge.

## Local and CI verification

Use Node 22 and the package's pinned pnpm. From the repository root:

```bash
pnpm --dir doc install --frozen-lockfile
npm ci --prefix artwork-resources/pcb-art/preview-source
cd doc
pnpm check:content
pnpm check
pnpm check:links -- --strict-broken --strict-absolute --strict-anchors
pnpm exec zfb wind audit --project-root . --fail-on error
GEN_DOC_HISTORY=1 pnpm build
pnpm check:links -- --strict-broken --strict-absolute --strict-anchors
pnpm check:images
pnpm check:viewers
pnpm check:redirects
pnpm exec wrangler deploy --dry-run --outdir /tmp/zudo-blanks-worker-dry-run
pnpm check:worker
cd ..
python3 -m pip install -r scripts/art-order/requirements.txt
python3 artwork-resources/pcb-art/manufacturing/verify_ordered.py
```

Use the personal heavy-test guard around a local production build or browser suite
when that guard is installed. GitHub-hosted CI uses an isolated runner and a job
timeout. The documentation workflow tests PR merge commits against **any target
branch**, including stack bases, and reruns on `edited` (retargeting). It also runs
on `main` pushes. It records head/base/tested revisions, fetches full Git history,
and does not need Cloudflare or deployment credentials. Leave history-skip
variables unset. `GEN_DOC_HISTORY=1` includes history JSON in local built reviews.
The independent manufacturing workflow retains its regression suites and archive
integrity guard; native fabrication generation remains an explicit manual task.

`check:content` covers dynamic inventory and generated-output drift without KiCad,
Pillow or macOS `sips`. Normal builds reuse committed images. Native board image
regeneration is a separate, intentional maintenance task; never refresh frozen
geometry or retained order files to make a docs check pass.

For interactive review, run `pnpm exec wrangler dev --local` from `doc/` after a
build. Review desktop/mobile and light/dark pages; search; History/Compare;
transitions; sidebar focus, broaden and restore; direct reloads; query/hash links;
all viewer controls including Kumiko wide/standard and Strip Mine pattern 5,
Strata/blobs; representative redirects; and model downloads. Confirm a missing
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
requests addressed to that hostname. Redirect to the new root while retaining the
suffix and query, then apply the committed new-host route mappings. Fragments are
not sent to servers; avoid adding or replacing fragments in redirect locations
unless an explicit anchor migration requires it. Test old deep links, viewer
selection queries and browser-held hashes before switching old-host traffic.
Retiring this repository's Netlify tooling does not remove or modify that host.

## Stack integration

The docs branch starts after parent commit
`f31c49d3cad0364033c18d4f91d07139ea4872f5` on
`chore/completed-four-art-order` (PR #27). Its initial draft PR targets that branch.
The final target is `main`. After a separately authorized and verified merge of
#27, fetch fresh `main`, identify **only** the docs commits after the recorded
parent boundary, and transplant those commits onto fresh `main`. A squash/rebase
merge changes parent commit IDs: do not replay the old #27 commits. Review the
resulting diff and completed-order download references, retarget the PR, and rerun
relevant checks against its actual head/base. Closed-unmerged is not delivery;
reconcile any content decision explicitly. Keep #22 and #25 open until integration
is authorized and completed.

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
activation opt-in variable; never deploy from PRs or the stack parent branch.
Validate production page content, real 404s, downloads, history, viewers and
redirects after activation. Record the deployed version and preceding version for
rollback. Rollback to that previously verified Worker version is another remote
operation and requires authorization; do not revert or regenerate the order archive.
