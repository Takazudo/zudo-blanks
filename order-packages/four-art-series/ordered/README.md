# Completed four-series order

The owner reported the order completed on **2026-10-10 JST**. Accepted choice **B** uses compact grouped lowers with the **red6+4 split**, at **25 complete stacks per series**: Coral Vault, Fault Line, Kumiko Void **wide**, and Spider Nest. The cart had **13 lines, each quantity 25**, yielding **100 finished artworks / 850 useful PCB pieces** with no blank cells or surplus.

[Open the exact PCBs, CAM previews and order ZIPs](OPEN.md) · [Original quantity/settings table](bundle/variants/split-red/ORDER.md) · [Machine-readable cart and completion evidence](completion.json) · [Nominal stack sides](bundle/previews/nominal-stack-sides.png)

The last verified quote was **¥204,169 = ¥189,963 manufacturing + ¥14,206 shipping**. This comes from the supplied task context and is a **quote, not a receipt or final paid amount**. No order ID, actual order timestamp, receipt, payment details or raw local quote file was supplied. The report date above does not establish the actual transaction date. This archive does not instruct another purchase.

## Retained fabrication set

- Exactly 34 original source boards/projects: four unchanged individually routed cosmetic tops and 30 lowers. All match the committed `panels/` sources.
- Six editable grouped lower sheets: white HASL, black ENIG, green HASL, black HASL, red six and red Fault Line four. Purple, yellow and blue lowers remain individual. Black ENIG stays separate from black lead-free HASL.
- Exactly 13 adopted order ZIPs, with their original CAM bytes, source/project hashes, placement records, DRC evidence, manufacturing settings and useful source/CAM/stack previews.
- FR-4, 1.6 mm, two copper layers, 1 oz; source apertures/mounts/artwork unchanged; translation-only lower placement with 5 mm rails. Tops are routed; V-scores are separate fabrication drawings. Detailed original settings are in the linked table and `FABRICATION.txt` files.

## Provenance and verification

The bytes come from [run 37833323671](https://github.com/Takazudo/zudo-blanks/actions/runs/37833323671), tested source `27481603195bb1318a0086d119294a5725dd36a0`, artifact `art-order-four-art-series-all-37833323671-1`, retained by [PR #26](https://github.com/Takazudo/zudo-blanks/pull/26) at main `daca5d44e5b6ec382481a1c1e9a3e634b04381ea`.

[Original run receipt](bundle/receipt.json), [original full-bundle checksums](provenance/original-SHA256SUMS), and copied `bundle/inputs/` tool/profile evidence remain unchanged. These historical records describe the pre-order three-alternative run, including its then-pending factory checks. They do not establish supplier approval, physical fit or payment. `bundle/individual-verification.json` retains source verification for all 34 native inputs; unused individual ZIP references in that historical record refer to abandoned exports removed from this tree.

[Retention mapping](retention.json) describes only the adopted subset. Raw CAM duplicated in adopted ZIPs is restored for verification; original local editor state is encoded, with new window state ignored. `bundle/SHA256SUMS` describes that reconstructed subset. [SHA256SUMS](SHA256SUMS) covers the physical archive, including new completion metadata and navigation. Every retained original run file is checked against `provenance/original-SHA256SUMS`; no PCB, project, CAM, order ZIP or original order manifest was regenerated or edited.

Run from the repository root:

```sh
/tmp/art-order-venv/bin/python artwork-resources/pcb-art/manufacturing/verify_ordered.py
```

See [setup and generation guidance](../../../scripts/art-order/README.md). Verification checks exact source/native membership, geometry partition, DRC bindings, ZIP/CAM completeness, settings, quantities, original provenance and current checksums. It does not repeat KiCad exports or the exhaustive width certificate, and does not verify supplier acceptance or delivered physical boards.

## Cleanup and source boundaries

[Machine-readable cleanup inventory](provenance/cleanup.json) records retained original paths and removed old paths. `current/` was replaced by `ordered/`; the individual-board baseline and grouped red10 generated candidate trees, their ZIPs/tables/previews, and unused individual CAM exports were removed. No tracked 100-stack generated candidate package was found. Those abandoned outputs remain recoverable in Git history.

Original artwork, all `panels/` designs (including standard Kumiko and Woven Maze), historical five-series grouped sources/profiles, generators, manufacturing policy and design/3D previews remain in their existing source directories. Strip Mine files and prior order documentation are preserved completely. Ordinary Git stores this archive; no LFS, remote purge, history rewrite or Actions-only storage is used.

This completed archive is frozen. Future generation uses fresh ignored output directories and cannot replace it without an explicit reviewed change. Historical comparison support remains in the generators for reproducibility; it is not the canonical ordered dataset.
