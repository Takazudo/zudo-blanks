# zudo-blanks

Blank panel PCB designs for modular synthesizers. These are simple PCBs with no electronic components - just blank panels with mounting holes and optional silkscreen artwork.

## Overview

This project contains KiCad PCB designs for blank panels in various HP widths for Eurorack format modular synthesizers. The panels are designed for manufacturing via JLCPCB.

## Documentation

- **Documentation site**: Built with Docusaurus
- **Development**: `cd doc && pnpm install && pnpm start`
- **URL**: `http://zblanks.localhost:43621/pj/zblanks/`

## Repository Structure

- `blank-panels.kicad_pro` - KiCad project file
- `blank-panels.kicad_sch` - KiCad schematic (minimal, for blank panels)
- `blank-panels.kicad_pcb` - KiCad PCB layout
- `footprints/` - KiCad footprint library
- `symbols/` - KiCad symbol library (placeholder)
- `doc/` - Docusaurus documentation site
- `.github/` - GitHub Actions CI/CD

## Workflow

1. Design panel in KiCad (Edge.Cuts outline, mounting holes, silkscreen)
2. Export Gerber files
3. Order from JLCPCB
