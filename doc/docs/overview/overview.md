---
sidebar_position: 2
slug: project-overview
---

# Project Overview

Blank panel PCB designs for modular synthesizers. These panels have no electronic components - they are simple PCBs used to fill empty spaces in Eurorack cases.

## Design Goals

### Panel Specifications

- **Format**: Eurorack (3U height, 128.5mm)
- **Material**: FR-4 PCB, 1.6mm thickness
- **Mounting**: Standard Eurorack M3 mounting holes
- **Surface**: Optional silkscreen artwork

### Manufacturing

- **Manufacturer**: JLCPCB
- **Minimum order**: 5 pieces
- **Surface finish**: HASL (lead-free)

## Panel Sizes

Eurorack panels are measured in HP (Horizontal Pitch), where 1 HP = 5.08mm.

| HP  | Width (mm) | Common Use        |
| --- | ---------- | ----------------- |
| 2   | 10.16      | Narrow gap filler |
| 4   | 20.32      | Small gap filler  |
| 6   | 30.48      | Standard blank    |
| 8   | 40.64      | Standard blank    |
| 10  | 50.80      | Medium blank      |
| 12  | 60.96      | Medium blank      |
| 16  | 81.28      | Large blank       |
| 20  | 101.60     | Large blank       |

## Design Elements

### Edge.Cuts

The board outline defines the panel dimensions. All panels use:

- **Height**: 128.5mm (3U standard)
- **Width**: HP x 5.08mm
- **Corner radius**: Optional rounded corners

### Mounting Holes

Standard Eurorack mounting holes:

- **Diameter**: 3.2mm (for M3 screws)
- **Position**: 3mm from top/bottom edges, 7.5mm from side edges
- **Spacing**: One pair at top, one pair at bottom

### Silkscreen

Optional decorative elements on F.Silkscreen and B.Silkscreen layers:

- Project name or logo
- Decorative patterns
- Version markings

## Workflow

1. **Design** panel in KiCad PCB editor
2. **Define** Edge.Cuts outline for desired HP width
3. **Place** mounting holes
4. **Add** silkscreen artwork (optional)
5. **Export** Gerber files
6. **Order** from JLCPCB

## Next Steps

1. Design panels in various HP widths
2. Add custom silkscreen artwork
3. Export Gerber files and order from JLCPCB
