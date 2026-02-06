# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a hardware project for designing blank panels for modular synthesizers. Unlike circuit-based projects, this contains **no electronic components, no BOM, no circuit design** - just blank PCB panels with mounting holes and optional silkscreen artwork. The panels are designed for manufacturing via JLCPCB.

## Deployment

The documentation is automatically deployed to Netlify:

- **Production URL**: https://takazudomodular.com/pj/zblanks/
- **Base Path**: `/pj/zblanks/`
- **Deployment**: Automatic on every push to `main` branch
- **Technology**: Docusaurus static site deployed via Netlify CLI on GitHub Actions
- **Configuration**: See `.github/workflows/main-deploy.yml` for deployment workflow

## Repository Structure

For the full file structure documentation, see `/doc/docs/overview/file-structure.md`.

### Key Directories
- `/panels/` - **All KiCad panel projects** (flat structure, one dir per panel)
  - `alumi-blanks-v1-{format}-{hp}/` - Plain aluminum blank panels
  - `art-{name}/` - Decorated art panels
  - `saucer{N}-{design}-{hp}/` - Saucer series panels
- `/footprints/` - **Shared KiCad footprint library**
- `/symbols/` - **Shared KiCad symbol library** (minimal)
- `/artwork-resources/` - **Source artwork files** (AI, SVG)
- `/jlcpcb-order-snapshots/` - **JLCPCB order history** (`{date}-{panel}/`)
- `/doc/` - **Docusaurus documentation site**
- `/__inbox/` - **Temporary files** (gitignored)

## Documentation Language

**All documentation must be written in English.** This includes:
- Technical specifications
- README files
- Code comments
- Commit messages

Use English for all text to ensure international accessibility and collaboration.

## URL Reference Guidelines

When the user provides URLs starting with `http://localhost:43621/pj/zblanks/` or `http://zblanks.localhost:43621/pj/zblanks/` in the conversation:

- **DO NOT fetch the URL** - These are local documentation URLs served by Docusaurus
- **Instead, find and read the corresponding markdown file** in the `/doc/` directory
- Map URLs to file paths following Docusaurus routing (note: `/pj/zblanks/` is the base path):
  - `http://zblanks.localhost:43621/pj/zblanks/` → `/doc/docs/` (root pages)
  - `http://zblanks.localhost:43621/pj/zblanks/docs/inbox/overview` → `/doc/docs/inbox/overview.md`
- Use the Read tool to access the actual markdown source files

## File Types

- `.md` files contain technical specifications in text format
- `.kicad_pro` - KiCad project configuration file
- `.kicad_sch` - KiCad schematic files
- `.kicad_pcb` - KiCad PCB layout files
- `.kicad_mod` - KiCad footprint files (physical component pads)
- `.kicad_sym` - KiCad symbol library files (schematic symbols)
- `fp-lib-table` - Footprint library configuration
- `sym-lib-table` - Symbol library configuration
- No code compilation or testing is required - this is a hardware design project

## Directory-Scoped CLAUDE.md Files

Subdirectories with their own conventions have dedicated CLAUDE.md files:
- `/doc/CLAUDE.md` - Docusaurus sidebar structure, adding pages, dev commands
- `/footprints/CLAUDE.md` - Footprint file organization, SVG export workflow
