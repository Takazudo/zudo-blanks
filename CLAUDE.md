# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a hardware project for designing blank panels for modular synthesizers. Unlike circuit-based projects, this contains **no electronic components, no BOM, no circuit design** - just blank PCB panels with mounting holes and optional silkscreen artwork. The panels are designed for manufacturing via JLCPCB.

## Documentation delivery

The documentation uses published zudo-doc 6.0.2, zfb 4.3.2, and the Cloudflare
Workers Static Assets adapter. Its prepared URL is https://zudo-blanks.zudolab.dev
with base `/`. Validation is credential-free; no automatic remote deployment is
configured. Production activation and the old-host cutover remain a separate
authorized operation on verified `main`. See `doc/OPERATIONS.md` and
`.github/workflows/docs.yml`.

## Repository Structure

For the full file structure documentation, see `/doc/src/content/docs/overview/file-structure.md`.

### Key Directories
- `/panels/` - **All KiCad panel projects** (flat structure, one dir per panel)
- `/_3dp/` - **Printable accessory projects**, outside the panel inventory
  - `alumi-blanks-v1-{format}-{hp}/` - Plain aluminum blank panels
  - `art-{name}/` - Decorated art panels
  - `saucer{N}-{design}-{hp}/` - Saucer series panels
- `/footprints/` - **Shared KiCad footprint library**
- `/symbols/` - **Shared KiCad symbol library** (minimal)
- `/artwork-resources/` - **Source artwork files** (AI, SVG)
- `/jlcpcb-order-snapshots/` - **JLCPCB order history** (`{date}-{panel}/`)
- `/order-packages/four-art-series/ordered/` - Frozen completed four-series order deliverables and provenance; source/generation material remains in panels and artwork-resources
- `/doc/` - **zudo-doc documentation site**
- `/__inbox/` - **Temporary files** (gitignored)

## Documentation Language

**All documentation must be written in English.** This includes:
- Technical specifications
- README files
- Code comments
- Commit messages

Use English for all text to ensure international accessibility and collaboration.

## URL Reference Guidelines

Local documentation runs at `http://localhost:4321/`. Read corresponding source
files rather than fetching a user's localhost URL. `/docs/panels/` maps to
`doc/src/content/docs/panels/index.mdx`; the homepage uses package-owned home
components. Historical `/pj/zblanks/` URLs belong to the old host and compatibility
mapping, never a new asset prefix.

## File Types

- `.md` files contain technical specifications in text format
- `.kicad_pro` - KiCad project configuration file
- `.kicad_sch` - KiCad schematic files
- `.kicad_pcb` - KiCad PCB layout files
- `.kicad_mod` - KiCad footprint files (physical component pads)
- `.kicad_sym` - KiCad symbol library files (schematic symbols)
- `fp-lib-table` - Footprint library configuration
- `sym-lib-table` - Symbol library configuration
- Documentation code requires `pnpm check`, link checks, and a static build under `doc/`

## Directory-Scoped CLAUDE.md Files

Subdirectories with their own conventions have dedicated CLAUDE.md files:
- `/doc/CLAUDE.md` - zudo-doc navigation structure, adding pages, dev commands
- `/footprints/CLAUDE.md` - Footprint file organization, SVG export workflow
