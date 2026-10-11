# zudo-blanks

Blank panel PCB designs for modular synthesizers. These are simple PCBs with no electronic components - just blank panels with mounting holes and optional silkscreen artwork.

## Overview

This project contains KiCad PCB designs for blank panels in various HP widths for Eurorack format modular synthesizers. The panels are designed for manufacturing via JLCPCB.

## Documentation

- **Documentation site**: Built with zudo-doc
- **Development**: `cd doc && pnpm install --frozen-lockfile && pnpm dev`
- **URL**: `http://localhost:4321/pj/zblanks/`

## Repository Structure

- `panels/` - All KiCad panel projects (one directory per panel)
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

## Documentation build and deployment

The site is a static zudo-doc export in `doc/dist/`. GitHub Actions installs the pinned pnpm lockfile with Node 22, checks the docs, builds `dist/`, and stages it at `deploy-dir/pj/zblanks/` for the existing Netlify site. Production remains at https://takazudomodular.com/pj/zblanks/.

The migration used `create-zudo-doc@5.26.5` (`pnpm create zudo-doc /tmp/zblanks-zudo-doc-13 --yes --lang en --no-i18n --no-git --no-install --claude-resources`) in a scratch directory. The config keeps the starter defaults except for site identity, base path, repository-scoped Claude resources, navigation, and strict broken-link reporting. `--claude-resources` publishes project `.claude/skills`; it does not install zudo-doc's authoring skills. To roll back, revert the documentation migration commit(s) and redeploy the prior Docusaurus build.

### Published route migration

| Previous URL below `/pj/zblanks/` | New URL | Handling |
| --- | --- | --- |
| `/docs/overview` | `/docs/overview` | Preserved |
| `/docs/overview/project-overview` | same | Preserved by filename |
| `/docs/overview/file-structure` | same | Preserved |
| `/docs/how-to/*`, `/docs/misc`, `/docs/inbox` | same | Preserved |
| `/docs/{overview,how-to,misc,inbox}/index` | `/docs/{section}` | Netlify 301 redirects |
| `/` at the Netlify site root | `/pj/zblanks/` | Netlify 301 redirect |

The catalog, manufacturing, workflow, and Claude sections are new. The final catalog content is maintained with the corresponding panel work.

## Saved PCB art order candidates

[Open the completed four-series order](order-packages/four-art-series/ordered/README.md): Coral Vault, Fault Line, Kumiko Void wide and Spider Nest, with compact grouped lowers and the red6+4 split. The owner reported completion on 2026-10-10 JST: 25 stacks per series, 100 artworks / 850 useful PCB pieces, 13 lines at quantity 25. The retained fabrication files are committed in ordinary Git. The last verified quote was ¥204,169 (¥189,963 manufacturing + ¥14,206 shipping); this is not a receipt or final paid amount.
