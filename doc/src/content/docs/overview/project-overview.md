---
title: Project Overview
sidebar_position: 2
---

This repository holds KiCad PCB panels for modular synthesizers. Its [catalog](/docs/panels/) covers every current project directory: plain blanks and adapters, side frames, Saucer designs, earlier artwork and six layered art families. The panels are decorative or structural; they contain no active electronic circuit.

The plain and older art directories have varied board geometry, finishes and order histories. Read each native board and any local README before using it; a directory name's HP value is a nominal module width, not a promise that the routed edge measures exactly `HP × 5.08 mm`. The catalog does not assert a common finish or approval state for those historical projects.

## Layered artwork and completed orders

The historical five-design selection comprises 43 boards: [Spider Nest](/docs/panels/art/spider-nest/), [Coral Vault](/docs/panels/art/coral-vault/), [Fault Line](/docs/panels/art/fault-line/), [Kumiko Void wide](/docs/panels/art/kumiko-void/) and [Woven Maze](/docs/panels/art/woven-maze/). Each top is nominally 101.3 × 128.5 mm, and lower boards are shorter to clear the rail regions. The stack has 1.6 mm boards separated by 3.0 mm spacers. Exact slot and support coordinates are in the [engineering dimensions](/docs/guides/engineering/dimensions/).

The 3D viewer shows Revision 5 visual design intent. The selected native boards incorporate local router, copper and mask adjustments. Native KiCad DRC/CAM and historical grouped-sheet checks are recorded. The owner reported the four-series order completed on 2026-10-10 JST: Spider Nest, Coral Vault, Fault Line and Kumiko Void wide. The frozen archive retains 13 adopted ZIPs and 34 source boards. Woven Maze is outside that order, and standard Kumiko remains reference-only. Supplier acceptance and physical assembly of the four series are not established by these local checks. Strip Mine has separate prior-order and owner-reported assembly evidence.

<a href="/viewers/pcb-art/">Interactive design viewer</a> · [Manufacturing status](/docs/manufacturing/) · [Package plan](/docs/manufacturing/order/)
