# KiCad Blank Panel Workflow

Workflow for designing blank panels in KiCad, from PCB layout to manufacturing files.

## Prerequisites

**CRITICAL:** Ensure your KiCad project files are located at the repository root:

```
zudo-blanks/          ← Repository root
├── blank-panels.kicad_pro       ← Project file must be here
├── blank-panels.kicad_sch       ← Schematic file (minimal)
├── blank-panels.kicad_pcb       ← PCB file
└── footprints/                  ← Footprint library
    └── kicad/
```

## Overview

Blank panels are simple PCB designs that skip most of the traditional KiCad workflow. Since there are no electronic components, you work primarily in the PCB Editor:

1. **PCB Editor** - Design the panel (outline, mounting holes, silkscreen)
2. **Manufacturing Output** - Generate Gerber files
3. **Order** - Upload to JLCPCB

## Stage 1: PCB Layout

### 1.1 Set Board Dimensions (Edge.Cuts)

1. Open the PCB file in **PCB Editor**
2. Select **Edge.Cuts** layer
3. Draw board outline:
   - **Height**: 128.5mm (Eurorack 3U standard)
   - **Width**: HP x 5.08mm (e.g., 8HP = 40.64mm)

**Using the drawing tools:**

- Press `Ctrl+Shift+P` for polygon tool, or use line tool
- Enter exact coordinates in the properties panel for precision
- Ensure the outline is a closed shape

### 1.2 Place Mounting Holes

Add standard Eurorack M3 mounting holes:

1. Place footprint: Use a 3.2mm mounting hole footprint
2. Position holes:
   - **Top-left**: X=7.5mm from left edge, Y=3mm from top
   - **Top-right**: X=7.5mm from right edge, Y=3mm from top
   - **Bottom-left**: X=7.5mm from left edge, Y=3mm from bottom
   - **Bottom-right**: X=7.5mm from right edge, Y=3mm from bottom

For narrow panels (2-4 HP), use only one pair of holes (top and bottom center).

### 1.3 Add Silkscreen (Optional)

Decorative elements on F.Silkscreen layer:

1. Select **F.Silkscreen** layer
2. Add text, lines, or import graphics
3. Common elements:
   - Panel name or logo
   - Decorative borders
   - Version marking (small, bottom corner)

**Best practices:**

- Keep silkscreen away from mounting holes (1mm clearance)
- Use minimum 0.8mm text height for readability
- Test artwork visibility on dark solder mask colors

### 1.4 Design Rule Check (DRC)

Before generating output:

1. Inspect → Design Rules Checker
2. Run DRC
3. Fix any issues:
   - Board outline must be closed
   - Mounting holes properly placed
   - No silkscreen overlapping holes

## Stage 2: Manufacturing Output

### 2.1 Generate Gerber Files

1. File → Fabrication Outputs → Gerbers (.gbr)
2. Settings:
   - Include layers: F.Cu, B.Cu, F.Mask, B.Mask, F.Silkscreen, B.Silkscreen, Edge.Cuts
   - Coordinate format: 4.6, unit mm
   - Check "Use Protel filename extensions"
3. Click "Plot"

### 2.2 Generate Drill Files

1. File → Fabrication Outputs → Drill Files (.drl)
2. Settings:
   - Drill units: Millimeters
3. Click "Generate Drill File"

### 2.3 Verify with Gerber Viewer

1. Open **GerbView** (included with KiCad)
2. Load all Gerber files + drill file
3. Check:
   - Board outline correct dimensions
   - Mounting holes visible and correctly positioned
   - Silkscreen readable (not over holes)
   - Layers aligned correctly

## Stage 3: Order from JLCPCB

### 3.1 Prepare Files

Create ZIP archive with:

- All Gerber files (.gbr)
- Drill file (.drl)

```bash
# Example ZIP structure
gerbers.zip
├── F_Cu.gbr
├── B_Cu.gbr
├── F_Mask.gbr
├── B_Mask.gbr
├── F_Silkscreen.gbr
├── B_Silkscreen.gbr
├── Edge_Cuts.gbr
└── drill.drl
```

### 3.2 Upload and Configure

1. Go to [jlcpcb.com](https://jlcpcb.com)
2. Upload gerbers.zip
3. Configure:
   - PCB quantity: 5 (minimum)
   - PCB thickness: 1.6mm (standard)
   - Surface finish: HASL (lead-free)
   - PCB color: Choose solder mask color (green, black, white, etc.)
   - No assembly needed (blank panels have no components)

## Workflow Summary

```
1. PCB Editor → Draw Edge.Cuts outline
   ↓
2. Place mounting holes
   ↓
3. Add silkscreen artwork (optional)
   ↓
4. DRC Pass
   ↓
5. Generate Gerber + Drill files
   ↓
6. Verify in GerbView
   ↓
7. Order from JLCPCB
```

## Troubleshooting

### Common Issues

**Problem:** DRC shows "board outline not closed"

- **Solution:** Ensure all Edge.Cuts lines form a complete closed shape with no gaps

**Problem:** Mounting holes not appearing in Gerber

- **Solution:** Verify drill file was generated separately from Gerbers

**Problem:** Silkscreen not visible on manufactured board

- **Solution:** Check minimum line width (0.15mm) and text height (0.8mm) for JLCPCB

## References

- [KiCad Documentation](https://docs.kicad.org/)
- [JLCPCB PCB Capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)
- [Eurorack Mechanical Specifications](https://doepfer.de/a100_man/a100m_e.htm)
