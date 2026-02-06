---
sidebar_position: 2
---

# Download KiCad Footprints

This guide explains how to download KiCad footprints from LCSC/EasyEDA using the easyeda2kicad.py tool. For blank panels, you primarily need mounting hole footprints.

## Overview

This project uses [easyeda2kicad.py](https://github.com/uPesy/easyeda2kicad.py) to download KiCad libraries from the LCSC/EasyEDA database when needed.

**For blank panels, you mainly need:**

- **Mounting hole footprints** - Standard M3 through-hole mounting holes
- KiCad's built-in libraries already include standard mounting holes

## Using KiCad Built-in Mounting Holes

KiCad includes mounting hole footprints in its standard library:

1. Open **Footprint Editor**
2. Browse library: `MountingHole`
3. Common footprints:
   - `MountingHole_3.2mm_M3` - Standard M3 mounting hole
   - `MountingHole_3.2mm_M3_Pad` - M3 with copper pad
   - `MountingHole_3.2mm_M3_Pad_Via` - M3 with vias for grounding

## Prerequisites (for custom footprints)

### Install easyeda2kicad.py

```bash
pip install easyeda2kicad
```

### Verify Installation

```bash
easyeda2kicad --version
```

## Download Custom Footprints

If you need footprints not in KiCad's standard library:

```bash
# Download footprint by LCSC ID
easyeda2kicad --lcsc_id <LCSC_ID> --footprint

# Copy to project directory
cp ~/Documents/Kicad/easyeda2kicad/easyeda2kicad.pretty/*.kicad_mod ./footprints/kicad/
```

## Project Structure

```
footprints/
├── kicad/
│   └── *.kicad_mod          # KiCad footprint files
├── images/
│   └── *.svg                # Exported SVG images (for documentation)
└── scripts/
    └── clean-svg-refs.py    # Script to clean SVG exports
```

## Troubleshooting

### Problem: "easyeda2kicad: command not found"

**Solution**: Ensure pip installed the package correctly and it's in your PATH:

```bash
which easyeda2kicad
```

### Problem: "Part not found"

**Solution**:

- Verify the LCSC ID is correct
- Check if the part exists on LCSC.com

## References

- [easyeda2kicad.py GitHub](https://github.com/uPesy/easyeda2kicad.py)
- [LCSC Component Search](https://www.lcsc.com/)
- [KiCad Documentation](https://docs.kicad.org/)
