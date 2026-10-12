# doc/ — zudo-doc documentation

Use Node 22+, pinned pnpm 10.28.1, and the committed lockfile. The installed
packages are `@takazudo/zudo-doc` and `@takazudo/zudo-doc-history-server` 6.0.2,
with `@takazudo/zfb`, `@takazudo/zfb-runtime`, `@takazudo/zfb-md-wasm`, and
`@takazudo/zfb-adapter-cloudflare` 4.3.2. All content is English. The site root
is `/`; documentation routes retain `/docs/`.

Write pages in `src/content/docs/`. The five main sections are panels, models,
manufacturing, guides, and overview. Each directory has a meaningful `index.mdx`.
Use filesystem ancestry and the native Broader Tree; preserve contributor and
archive navigation. Use relative MDX links and add compatibility mappings whenever
moving a published page. Keep useful editorial prose outside generated regions.

Use native MDX/HTML and authored CSS. Intrinsic markup uses `class`, not
`className`. Released 6.0.1 accepts MDX components that declare required typed
props; this site keeps native MDX/HTML and has no custom-component registration.
Keep released CSS layers, package-base tsconfig and route seams, and
`DocHistoryBoundary` integration. Published 6.0.2 has no `initialPathMode`
sidebar option, so the native filesystem hierarchy stays in place.

Project Claude resources are generated from repository instructions and skills;
do not edit generated `claude-*` pages or publish machine-global skills. Keep
history, comparison and generated history JSON; leave history-skip variables unset.
`scripts/reconcile-history.mjs` restores original dates and canonical revisions
for pages moved across content roots, using the published history API and
`data/route-migration.json`. Remove that helper only after a published upstream
fix passes the same original-date and History/Compare checks.

`pnpm check:content` verifies fast metadata/content drift. `pnpm check:accessories`
checks printable sources under `_3dp/` separately from the panel inventory.
Supported files (`.3mf`, `.stl`, `.step`, `.stp`, `.fcstd`) need a download
mapping in `scripts/stage_viewers.mjs` or a reasoned exclusion. Preview generation
from native KiCad sources is separate; builds reuse committed images. Canonical
viewer HTML lives under `/viewers/`, outside automatic asset-to-file-detail
rewriting. Keep local model indexing selected and deliberate; never copy the
frozen order archive wholesale into public assets.

See [OPERATIONS.md](OPERATIONS.md) for the complete source/built verification
sequence, full-history CI, local Wrangler review, route compatibility and
separately authorized production activation. Cloudflare root hosting is prepared
and credential-free validation covers the Worker. Production activation and the
old-host cutover remain a later authorized operation. No deployment, DNS change
or archive regeneration is implied by documentation maintenance.
