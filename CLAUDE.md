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

### Documentation
- `/doc/docs/` - **Primary documentation** (Docusaurus-based, organized)
  - `overview/` - Project overview
  - `how-to/` - How-to guides (KiCad workflow, parts download, SVG export)
  - `inbox/` - Quick reference and miscellaneous docs
  - `misc/` - Miscellaneous documentation
  - `_fragments/` - Reusable fragments
- `/doc/static/` - **Documentation assets** (images, SVGs)
  - `kicad/` - KiCad setup screenshots

### KiCad Libraries
- `/footprints/` - **KiCad footprint library**
  - `kicad/` - KiCad footprint source files (.kicad_mod)
  - `images/` - Exported SVG files (source for documentation)
  - `scripts/` - Processing scripts (clean-svg-refs.py)
- `/symbols/` - **KiCad symbol library** (placeholder, minimal for blank panels)

### KiCad Project Files (repository root)
- `blank-panels.kicad_pro` - Project configuration
- `blank-panels.kicad_sch` - Schematic (minimal for blank panels)
- `blank-panels.kicad_pcb` - PCB layout file

### Other Directories
- `/__inbox/` - **Temporary files** (gitignored, use for working files)

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

## KiCad Library Management

### File Organization

**Footprints (PCB physical pads):**
- **KiCad source files**: `/footprints/kicad/*.kicad_mod` (individual footprint files)
- **SVG exports**: `/footprints/images/*.svg` (intermediate)
- **Documentation SVGs**: `/doc/docs/_fragments/footprints/*.svg` (final destination)

### Exporting SVG Files for Documentation (Manual Workflow)

When footprints are added or updated, export SVGs manually for documentation:

**Quick workflow:**
```bash
# 1. Create .pretty directory if needed
cd footprints/kicad
mkdir -p zudo-blanks.pretty
cp *.kicad_mod zudo-blanks.pretty/

# 2. Export SVGs using KiCad CLI
kicad-cli fp export svg zudo-blanks.pretty -o ../images --black-and-white

# 3. Clean SVG files (remove REF** text)
python3 ../scripts/clean-svg-refs.py ../images/

# 4. Copy to documentation
cp ../images/*.svg ../../doc/docs/_fragments/footprints/
```

## Docusaurus Management

### Sidebar Structure

The documentation uses 4 sidebar sections defined in `/doc/sidebars.js`:
- **overviewSidebar** - Project overview
- **howToSidebar** - How-to guides
- **miscSidebar** - Miscellaneous
- **inboxSidebar** - INBOX (temporary workspace)

### Adding New Documentation Pages

1. Create `.md` or `.mdx` file in appropriate `/doc/docs/` subdirectory
2. Add the doc ID to the corresponding sidebar array in `/doc/sidebars.js`
3. If creating a new category, add corresponding entry in sidebar config

### Development Commands

```bash
cd doc
pnpm install          # Install dependencies
pnpm start            # Dev server (port 43621, zblanks.localhost)
pnpm run check        # Run typecheck + lint + format check
pnpm run build        # Production build
```
