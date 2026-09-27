---
title: Project Overview
sidebar_position: 2
---

This repository holds KiCad PCB panels for modular synthesizers. Its [catalog](../catalog/) covers every current project directory: plain blanks and adapters, side frames, Saucer designs, earlier artwork and five newer layered art stacks. The panels are decorative or structural; they contain no active electronic circuit.

The plain and older art directories have varied board geometry, finishes and order histories. Read each native board and any local README before using it; a directory name's HP value is a nominal module width, not a promise that the routed edge measures exactly `HP × 5.08 mm`. The catalog does not assert a common finish or approval state for those historical projects.

## Five layered art designs

The selected set comprises 43 boards: [Spider Nest](../designs/spider-nest.mdx), [Coral Vault](../designs/coral-vault.mdx), [Fault Line](../designs/fault-line.mdx), [Kumiko Void wide](../designs/kumiko-void.mdx) and [Woven Maze](../designs/woven-maze.mdx). Each top is nominally 101.3 × 128.5 mm, and lower boards are shorter to clear the rail regions. The stack has 1.6 mm boards separated by 3.0 mm spacers. Exact slot and support coordinates are in the [engineering dimensions](../engineering/dimensions.mdx).

The 3D viewer shows Revision 5 visual design intent. The selected native boards incorporate local router, copper and mask adjustments. Native KiCad DRC/CAM and grouped sheet checks passed locally; factory CAM, quotes, finish availability and physical fit remain pending. No purchase or manufacturer acceptance is recorded.

<a href="/assets/pcb-art/previews/index.html">Interactive design viewer</a> · [Manufacturing status](../manufacturing/) · [Package plan](../manufacturing/order.mdx)
