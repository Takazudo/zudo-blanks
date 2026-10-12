# zudo-blanks

Blank panel PCB designs for modular synthesizers. These are simple PCBs with no electronic components - just blank panels with mounting holes and optional silkscreen artwork.

## Overview

This project contains KiCad PCB designs for blank panels in various HP widths for Eurorack format modular synthesizers. The panels are designed for manufacturing via JLCPCB.

## Documentation

The zudo-doc 6.0.2 site organizes [Panels](doc/src/content/docs/panels/index.mdx),
[3D & Files](doc/src/content/docs/models/index.mdx),
[Manufacturing](doc/src/content/docs/manufacturing/index.mdx),
[Guides](doc/src/content/docs/guides/index.mdx), and
[About](doc/src/content/docs/overview/index.mdx).

The prepared production URL is https://zudo-blanks.zudolab.dev (activation is
separate). Develop with `cd doc && pnpm install --frozen-lockfile && pnpm dev` at
`http://localhost:4321/`. Browse family pages for every width/revision and use the
3D index for the canonical PCB art and Strip Mine viewers.

## Repository Structure

- `panels/` - All KiCad panel projects (one directory per panel)
- `_3dp/` - Printable accessory projects, published separately from the panel inventory
- `footprints/` - Shared KiCad footprint library
- `symbols/` - KiCad symbol library (minimal)
- `artwork-resources/` - Source artwork files (AI, SVG)
- `jlcpcb-order-snapshots/` - JLCPCB order history
- `doc/` - zudo-doc documentation site
- `.github/` - GitHub Actions CI/CD

## Workflow

1. Design panel in KiCad (Edge.Cuts outline, mounting holes, silkscreen)
2. Export Gerber files
3. Order from JLCPCB

## Documentation maintenance and delivery

[Operations and activation runbook](doc/OPERATIONS.md) covers frozen installs,
source/built link and anchor checks, inventory drift, printable-accessory
coverage, images, viewer and redirect checks, generated history, and local
built-Worker verification. CI checks each pull request's merge result and `main`
pushes. Full Git history is required. Metadata/content updates reuse committed
previews; native rendering is separate from ordinary documentation builds.

Cloudflare Workers Static Assets delivery is prepared and validated at the site
root. The adapter-generated `.assetsignore` is preserved. No workflow deploys
remotely. Production activation and the old-host cutover still require a
separately authorized, verified `main` revision. The old host's `/pj/zblanks/*`
redirect must be configured separately from compatibility redirects on the new
hostname. See the runbook for query/hash preservation. [PR #27](https://github.com/Takazudo/zudo-blanks/pull/27)
and [PR #28](https://github.com/Takazudo/zudo-blanks/pull/28) are merged.

## Completed PCB art order archive

[Open the completed four-series order](order-packages/four-art-series/ordered/README.md): Coral Vault, Fault Line, Kumiko Void wide and Spider Nest, with compact grouped lowers and the red6+4 split. The owner reported completion on 2026-10-10 JST: 25 stacks per series, 100 artworks / 850 useful PCB pieces, 13 lines at quantity 25. The retained fabrication files are committed in ordinary Git. The last verified quote was ¥204,169 (¥189,963 manufacturing + ¥14,206 shipping); this is not a receipt or final paid amount.
