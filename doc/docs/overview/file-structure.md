---
sidebar_position: 3
slug: file-structure
---

# File Structure

This document describes the repository directory and file structure conventions.

## Top-Level Directory Layout

```
zudo-blanks/
├── panels/                    # All KiCad panel projects (flat, one dir per panel)
├── footprints/                # Shared KiCad footprint library
├── symbols/                   # Shared KiCad symbol library (minimal)
├── artwork-resources/         # Source artwork files (AI, SVG)
├── jlcpcb-order-snapshots/    # JLCPCB order history snapshots
├── doc/                       # Docusaurus documentation site
└── __inbox/                   # Temporary working files (gitignored)
```

## panels/

All KiCad panel projects live under `panels/` in a **flat structure** (one directory depth only). Each subdirectory is a standalone KiCad project containing one panel PCB design.

### Naming Conventions

Panel directories follow these naming patterns by category:

#### Aluminum Blank Panels

Plain blank panels with no artwork. Named as `alumi-blanks-{version}-{format}-{hp}`.

```
panels/
├── alumi-blanks-v1-1U-1hp/
├── alumi-blanks-v1-1U-2hp/
├── ...
├── alumi-blanks-v1-1U-10hp/
├── alumi-blanks-v1-3U-1hp/
├── alumi-blanks-v1-3U-2hp/
├── ...
└── alumi-blanks-v1-3U-16hp/
```

- `v1` indicates the design version
- `1U` or `3U` indicates the Eurorack format
- `1hp`, `2hp`, etc. indicates the HP width

#### Art Panels

Decorated panels with custom artwork. Named as `art-{hp}-{name}` or `art-{name}`.

```
panels/
├── art-10hp-takazudo-modular/
├── art-12hp-sun/
├── art-ufo/
└── art-ufo-v2/
```

#### Saucer Series

Artistic panel series. Named as `saucer{number}-{design-name}-{hp}`.

Each saucer design is available in multiple HP sizes (1hp, 2hp, 3hp, 4hp, 12hp).

```
panels/
├── saucer1-slow-wave-1hp/
├── saucer1-slow-wave-2hp/
├── saucer1-slow-wave-3hp/
├── saucer1-slow-wave-4hp/
├── saucer1-slow-wave-12hp/
├── saucer2-crystal-flow-1hp/
├── ...
└── saucer6-grainscape-12hp/
```

### Files Inside Each Panel Directory

Each panel directory contains KiCad project files. Gerber files and other manufacturing outputs are not stored here — they go in `jlcpcb-order-snapshots/` when ordered.

Typical contents:

```
panels/alumi-blanks-v1-3U-8hp/
├── 8hp.kicad_pcb          # PCB layout (the main design file)
└── 8hp.kicad_pro          # KiCad project configuration
```

Some art/saucer panels may also include:

- `svgs-for-import/` — SVG artwork files used for importing into KiCad layers
- `ufo-assets/` or similar — Design asset files specific to that panel

## artwork-resources/

Source artwork files (Adobe Illustrator `.ai`, SVG, PDF) used to create panel silkscreen designs. These are the original design files before being imported into KiCad.

```
artwork-resources/
└── 10hp-takazudo-modular/
    ├── 10hp-takazudo-modlar.ai
    ├── 10hp-takazudo-modlar.svg
    └── ...
```

## jlcpcb-order-snapshots/

Snapshots of files used for JLCPCB orders, organized by date and panel name.

```
jlcpcb-order-snapshots/
├── 2026-02-05-1hp/
│   ├── used-for-order/
│   │   └── gerbers/
│   └── from-order-detail/
├── 2026-02-05-2hp/
└── ...
```

Each snapshot directory is named `{date}-{panel-identifier}` and contains the exact files submitted for that order.

## footprints/

Shared KiCad footprint library used across all panel projects.

```
footprints/
├── kicad/                     # KiCad footprint source files (.kicad_mod)
├── images/                    # Exported SVG files
└── scripts/
    └── clean-svg-refs.py      # SVG cleanup script (removes REF** text)
```

## doc/

Docusaurus documentation site. See the [Project Overview](./project-overview) for panel specifications and design details.

```
doc/
├── docs/
│   ├── overview/              # Project overview docs
│   ├── how-to/                # How-to guides
│   ├── misc/                  # Miscellaneous docs
│   ├── inbox/                 # Temporary workspace
│   └── _fragments/            # Reusable doc fragments
├── static/                    # Static assets (images, SVGs)
├── src/                       # Docusaurus custom components
└── sidebars.js                # Sidebar configuration
```
