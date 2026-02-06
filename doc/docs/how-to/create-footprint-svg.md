---
sidebar_position: 3
---

# Create Footprint SVG Files for Documentation

This guide explains how to export KiCad footprints to SVG format and prepare them for use in the documentation.

## Overview

The documentation can display footprint previews. This workflow converts KiCad `.kicad_mod` files to clean SVG images.

## Prerequisites

- KiCad 9.0.6 or later (with `kicad-cli` command)
- Python 3 (for cleanup script)

## Verify KiCad CLI

```bash
kicad-cli --version
# Should show: Version: 9.0.6 or later
```

If `kicad-cli` is not found, you need to add it to your PATH:

**macOS:**

```bash
export PATH="/Applications/KiCad/KiCad.app/Contents/MacOS:$PATH"
```

## Workflow

### Step 1: Prepare .pretty Directory

KiCad CLI requires footprints in a `.pretty` directory structure:

```bash
cd footprints/kicad

# Create .pretty directory
mkdir -p zudo-blanks.pretty

# Copy .kicad_mod files
cp *.kicad_mod zudo-blanks.pretty/
```

### Step 2: Export to SVG

Export all footprints to SVG format with black-and-white rendering:

```bash
cd footprints

# Export SVGs
kicad-cli fp export svg kicad/zudo-blanks.pretty -o images --black-and-white
```

**Output:** SVG files are saved to `footprints/images/`

### Step 3: Clean SVG Files

Remove KiCad placeholder text (REF\*\*, VAL\*\*) from SVGs using the cleanup script:

```bash
cd footprints

# Run cleanup script
python3 scripts/clean-svg-refs.py images/
```

### Step 4: Copy to Documentation

```bash
cd footprints

# Copy cleaned SVGs to documentation fragments
cp images/*.svg ../doc/docs/_fragments/footprints/
```

## Directory Structure

```
project/
├── footprints/
│   ├── kicad/
│   │   ├── *.kicad_mod              # Original KiCad footprints
│   │   └── zudo-blanks.pretty/      # .pretty directory for export
│   │       └── *.kicad_mod
│   ├── images/
│   │   └── *.svg                    # Exported and cleaned SVGs
│   └── scripts/
│       └── clean-svg-refs.py        # Cleanup script
└── doc/
    └── docs/
        └── _fragments/
            └── footprints/
                └── *.svg            # Final SVGs for documentation
```

## Cleanup Script Details

### Location

`footprints/scripts/clean-svg-refs.py`

### What It Does

The script processes SVG files to remove KiCad placeholders:

1. **Text Elements**: Removes `<text>` elements containing `REF**` or `VAL**`
2. **Stroked-Text Groups**: Removes path-based text rendered as vector shapes
3. **Preserves**: All footprint geometry, pads, and silkscreen

### Usage

```bash
# Clean all SVGs in a directory
python3 clean-svg-refs.py /path/to/svg/directory/

# The script modifies files in-place
# Creates no backup - commit to git first!
```

## Troubleshooting

### Problem: kicad-cli not found

**Solution**: Add KiCad to PATH (see "Verify KiCad CLI" above)

### Problem: Export fails with "Library not found"

**Solution**: Ensure footprints are in a `.pretty` directory

### Problem: SVG still shows REF\*\* after cleanup

**Solution**:

1. Check that cleanup script ran successfully
2. Some SVGs may have additional text elements - inspect manually

## References

- [KiCad CLI Documentation](https://docs.kicad.org/master/en/cli/cli.html)
- [SVG Specification](https://www.w3.org/TR/SVG2/)
