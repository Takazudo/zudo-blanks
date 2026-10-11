# doc/ — zudo-doc documentation

Use Node 22+, pinned pnpm, published zudo-doc 6 and the committed lockfile. All
content is English. The site root is `/`; documentation routes retain `/docs/`.

Write pages in `src/content/docs/`. The five main sections are panels, models,
manufacturing, guides, and overview. Each directory has a meaningful `index.mdx`.
Use filesystem ancestry and the native Broader Tree; preserve contributor and
archive navigation. Use relative MDX links and add compatibility mappings whenever
moving a published page. Keep useful editorial prose outside generated regions.

Use native MDX/HTML and authored CSS. Intrinsic markup uses `class`, not
`className`; do not restore Preact aliases or custom components that depend on the
zudo-doc 6.0.0 required-props `mdxExtras` regression. Keep released CSS layers,
package-base tsconfig and route seams, and `DocHistoryBoundary` integration.

Project Claude resources are generated from repository instructions and skills;
do not edit generated `claude-*` pages or publish machine-global skills. Keep
history, comparison and generated history JSON; leave history-skip variables unset.

`pnpm check:content` verifies fast metadata/content drift. Preview generation from
native KiCad sources is separate; builds reuse committed images. Canonical viewer
HTML lives under `/viewers/`, outside automatic asset-to-file-detail rewriting.
Keep local model indexing selected and deliberate; never copy the frozen order
archive wholesale into public assets.

See [OPERATIONS.md](OPERATIONS.md) for the complete source/built verification
sequence, full-history CI, local Wrangler review, route compatibility and
separately authorized production activation. No merge, deployment, DNS change or
archive regeneration is implied by documentation maintenance.
