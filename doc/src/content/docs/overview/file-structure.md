---
title: Repository Structure
sidebar_position: 3
---

- [`panels/`](https://github.com/Takazudo/zudo-blanks/tree/main/panels) contains the top-level project directories indexed by the [catalog](../catalog/). Simple projects hold one KiCad board; layered art and grouped lower sheets contain multiple boards and may have nested project directories.
- [`artwork-resources/pcb-art/preview-source`](https://github.com/Takazudo/zudo-blanks/tree/main/artwork-resources/pcb-art/preview-source) holds the frozen Revision 5 visual geometry and interactive viewer sources.
- [`artwork-resources/pcb-art/manufacturing`](https://github.com/Takazudo/zudo-blanks/tree/main/artwork-resources/pcb-art/manufacturing) holds the fabrication policy, indexed corrections, local validation, native/CAM and package records.
- [`artwork-resources/pcb-art/resources`](https://github.com/Takazudo/zudo-blanks/tree/main/artwork-resources/pcb-art/resources) holds comparison images, review inputs and order planning sources.
- [`footprints/`](https://github.com/Takazudo/zudo-blanks/tree/main/footprints) and [`symbols/`](https://github.com/Takazudo/zudo-blanks/tree/main/symbols) hold shared KiCad libraries.
- `doc/` is the zudo-doc site. Its `public/assets` tree stages web copies from the canonical source data.
- [`.claude/skills/panel-preview`](https://github.com/Takazudo/zudo-blanks/tree/main/.claude/skills/panel-preview) documents preview maintenance for future panels.

[Panel inventory](../catalog/) · [Source of truth](../engineering/source-of-truth.mdx)
