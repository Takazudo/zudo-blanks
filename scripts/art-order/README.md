# Four-series order tools and completed archive

The canonical completed order is [order-packages/four-art-series/ordered](../../order-packages/four-art-series/ordered/README.md). The owner reported completion on 2026-10-10 JST, accepting choice B: compact grouped lowers, red6+4, 25 stacks each of Coral Vault, Fault Line, Kumiko Void wide and Spider Nest. Its 13 order ZIPs and unchanged native/CAM evidence are committed in ordinary Git.

Source/generation material stays in `panels/` and `artwork-resources/pcb-art/`; completed deliverables stay in `order-packages/`. `panels/art-grouped-lowers` and the existing manufacturing policy/records are historical five-series sources, including Woven Maze. Strip Mine is a separate already ordered project and remains untouched.

## Verify the completed archive

Install Python 3.13.7 and pinned dependencies in an isolated environment:

```sh
python3.13 -m venv /tmp/art-order-venv
/tmp/art-order-venv/bin/python -m pip install -r scripts/art-order/requirements.txt
/tmp/art-order-venv/bin/python artwork-resources/pcb-art/manufacturing/verify_ordered.py
```

No Docker, native regeneration, artifact download or local quote file is required. The verifier reconstructs duplicate CAM from the exact adopted ZIPs and original encoded KiCad local state in a temporary directory. It verifies 34 source board/project identities, six grouped native sheets and their geometry partition, DRC inputs/reports, original tool/profile hashes, actual CAM ZIP membership, exact 13-line quantity-25 accounting and original/current checksums. Editor state/locks/backups created when opening a PCB are ignored. Every retained original run file must match the original full-bundle checksum inventory. The full run receipt and source verification records remain historical and unchanged; their abandoned-alternative references do not describe additional retained packages.

`verify_ordered.py` verifies the selected subset using the same native/package validator as fresh bundles. The original receipt remains bound to its source/run; only the new subset checksum inventory and retention metadata describe cleanup. The archive's physical `SHA256SUMS` separately covers navigation, completion metadata and provenance. Do not use `retain_order_bundle.py --verify-saved` for this completed subset: that older tool reconstructs full historical candidate bundles.

Verification does not prove factory CAM/scoring approval, depanelization support, edge appearance, physical fit or final payment. The last verified ¥204,169 quote is recorded as a quote only in `completion.json`; no receipt/order ID was supplied.

## Generate disposable exports

Fresh generation is for development and verification. It never updates the completed archive or places orders. Docker and the pinned Linux KiCad 10.0.0 image in `pin.env` are required:

```sh
ART_ORDER_PYTHON=/tmp/art-order-venv/bin/python \
  bash scripts/art-order/run.sh \
  --profile artwork-resources/pcb-art/manufacturing/order-profiles/four-art-series.json \
  --variant split-red --output /tmp/four-art-series-development
```

Use a fresh empty output directory under `/tmp` or the ignored `artwork-resources/pcb-art/generated/` tree. The default is `split-red`; explicit `all`, `individual` and `grouped` modes retain historical comparison support. Their outputs are disposable candidates and must not be retained as canonical completed deliverables. The profile-aware lower builder also defaults to split-red; legacy no-profile generation retains its historical default. Never point generation at `order-packages/`.

The workflow runs focused regressions and frozen archive verification on pull requests. Manual dispatch optionally generates a fresh split-red bundle and uploads it for three days when `upload_bundle` is enabled. No workflow pushes files, replaces the archive, deploys or purchases anything. Exact source/head/base/run identity is recorded. Failure diagnostics expire after three days. Use an exact run/artifact, never an unspecified latest artifact:

```sh
gh run download RUN_ID --repo Takazudo/zudo-blanks \
  --name art-order-four-art-series-split-red-RUN_ID-ATTEMPT \
  --dir /tmp/four-art-series-downloaded
ART_ORDER_PYTHON=/tmp/art-order-venv/bin/python \
  bash scripts/art-order/run.sh --verify-bundle /tmp/four-art-series-downloaded \
  --expected-source TESTED_SOURCE_SHA --expected-run-id RUN_ID
```

Fresh bundles include all 34 source verification records and temporary individual reference CAM, even when the purchase list uses grouped lowers. Purchase membership always comes from the selected `variants/split-red/order.json`, never a directory-wide ZIP inventory. No purchase is requested by this cleanup.

The original run's KiCad workaround cyclically rotates complete serialized contour segments only for DRC copies of unchanged Spider L07 and Coral L03. Source/CAM inputs are unchanged. Grouped contour-seam rotations preserve complete primitives, UUIDs and coordinates, including one Fault L08 aperture for split-red. No rule, geometry or tolerance is relaxed. The exhaustive all-boundary artwork-width certificate stays opt-in.

## Ordinary Git storage

The completed archive is frozen, with four routed tops, three individual lower boards and six grouped sheets. Do not replace it with a fresh development bundle. An explicitly requested future order archive needs separate reviewed provenance and completion evidence. Keep retained assets in ordinary Git, without LFS or an outer Actions ZIP. The historical `retain_order_bundle.py` is retained for reproducing the old full-candidate storage format; it is not the completed-order updater.
