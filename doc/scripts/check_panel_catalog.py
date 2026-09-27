#!/usr/bin/env python3
"""Check that every repository panel has a real catalog link and preview."""

from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "doc"
RECORDS = json.loads((SITE / "data/panel-inventory.json").read_text())
CATALOG = (SITE / "src/content/docs/catalog/index.mdx").read_text()
DIRECTORIES = {path.name for path in (ROOT / "panels").iterdir() if path.is_dir()}
STACKS = {"art-spider-nest": 8, "art-coral-vault": 8, "art-fault-line": 9,
          "art-kumiko-void": 9, "art-woven-maze": 9, "art-grouped-lowers": 5}

assert len(RECORDS) == len(DIRECTORIES), "Inventory count differs from panels/"
assert {record["directory"] for record in RECORDS} == DIRECTORIES, "Panel inventory incomplete"
assert CATALOG.count('className="panel-card"') == len(DIRECTORIES), "Catalog card count differs"

for record in RECORDS:
    name = record["directory"]
    assert re.search(rf"https://github.com/Takazudo/zudo-blanks/tree/main/panels/{re.escape(name)}(?:\"|\))", CATALOG), name
    assert f"/{record['preview']}" in CATALOG, name
    assert record["boards"], name
    for board in record["boards"]:
        assert (ROOT / board).is_file(), board
    image = SITE / "public" / record["preview"]
    assert image.is_file(), image
    with Image.open(image) as preview:
        assert preview.width > 100 and preview.height > 100, image
    if name in STACKS:
        assert len(record["boards"]) == STACKS[name], name
        assert "local native DRC/CAM checked" in record["status"], name
    else:
        assert "status not established" in record["status"] or name == "art-strip-mine", name

viewer = SITE / "public/assets/pcb-art/previews/index.html"
assert viewer.is_file(), viewer
assert len(list(viewer.parent.glob("*.html"))) == 1, "Duplicate offline 3D viewers were staged"
for slug in ("spider-nest", "coral-vault", "fault-line", "kumiko-void", "woven-maze"):
    page = (SITE / "src/content/docs/designs" / f"{slug}.mdx").read_text()
    query = f"?design={slug}" + ("&amp;variant=wide" if slug == "kumiko-void" else "")
    assert f"previews/index.html{query}" in page, slug
    for board in next(r["boards"] for r in RECORDS if r["directory"] == f"art-{slug}"):
        assert f"https://github.com/Takazudo/zudo-blanks/blob/main/{board}" in page, board
    assert f"assets/panels/art-{slug}.png" in page, slug
assert "?design=kumiko-void&amp;variant=standard" in (SITE / "src/content/docs/designs/kumiko-void.mdx").read_text()
assert "reference only" in (SITE / "src/content/docs/designs/kumiko-void.mdx").read_text()
assert (ROOT / ".claude/skills/panel-preview/SKILL.md").is_file()
print(f"Catalog coverage passed: {len(DIRECTORIES)} directories, {len(STACKS)} multi-board overviews, one offline viewer")
