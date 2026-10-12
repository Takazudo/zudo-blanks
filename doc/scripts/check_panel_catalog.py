#!/usr/bin/env python3
"""Check complete native-file coverage, authored family destinations and metadata drift."""
from __future__ import annotations

import json
import struct
from pathlib import Path
from generate_panel_catalog import DOCS, ROOT, SITE, generated_outputs, inventory, native_board_paths

records = inventory()
expected = generated_outputs(records)
for path, content in expected.items():
    assert path.read_text() == content, f"Generated output drift: {path.relative_to(ROOT)}"
families = json.loads((SITE / "data/panel-pages.json").read_text())
assert len(families) == 19, "The curated family contract requires 19 families"
assert len({entry["slug"] for entry in families}) == len(families), "Duplicate family slug"
actual_boards = {str(path.relative_to(ROOT)) for path in native_board_paths(ROOT / "panels")}
recorded_boards = [board["path"] for record in records for board in record["boards"]]
assert len(recorded_boards) == len(set(recorded_boards)), "Native files counted twice"
assert set(recorded_boards) == actual_boards, "Recursive board coverage incomplete"
roles = {"panel source", "layer source", "reference alternative", "fabrication sheet", "test input"}
for record in records:
    page = DOCS / (record["family"] + ".mdx")
    text = page.read_text()
    assert f'id="{record["directory"]}"' in text, f"Missing variant anchor: {page}"
    assert f'/{record["preview"]}' in text, f"Missing preview: {page}"
    for board in record["boards"]:
        assert board["role"] in roles, board
        assert board["path"] in text and board["role"] in text, board
    image = SITE / "public" / record["preview"]
    data = image.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"Not a PNG: {image}"
    width, height = struct.unpack(">II", data[16:24])
    assert width > 100 and height > 100, image
catalog = (DOCS / "panels/index.mdx").read_text()
assert catalog.count('class="panel-card"') == len(families), "Family cards drifted"
for family in families:
    assert '/docs/panels/' + family['slug'] + '/' in catalog, family
    assert (DOCS / "panels" / (family["slug"] + ".mdx")).is_file(), family
for slug in ("spider-nest", "coral-vault", "fault-line", "kumiko-void", "woven-maze"):
    page = (DOCS / "panels/art" / f"{slug}.mdx").read_text()
    assert f'/viewers/pcb-art/?design={slug}' in page, slug
    assert 'class="viewer-frame"' in page and 'loading="lazy"' in page and 'title="' in page, slug
kumiko = (DOCS / "panels/art/kumiko-void.mdx").read_text()
assert "variant=wide" in kumiko and "variant=standard" in kumiko and "reference only" in kumiko
assert '/viewers/strip-mine/' in (DOCS / "panels/art/strip-mine.mdx").read_text()
# The completed cart is external, pinned, and exact; no entire archive copied into site assets.
completion = json.loads((ROOT / "order-packages/four-art-series/ordered/completion.json").read_text())
order_page = (DOCS / "manufacturing/order.mdx").read_text()
commit = "f31c49d3cad0364033c18d4f91d07139ea4872f5"
for package in completion["packages"]:
    assert f'{commit}/order-packages/four-art-series/ordered/bundle/{package["path"]}' in order_page, package
assert len(completion["packages"]) == 13
migration = json.loads((SITE / "data/route-migration.json").read_text())
assert len(migration["overlay"]) == 28, "Every overlay page needs a disposition"
for item in migration["overlay"]:
    assert item["disposition"], item
print(f"Catalog passed: {len(records)} directories, {len(recorded_boards)} native files, {len(families)} families, 28 overlay dispositions; metadata drift clean")
