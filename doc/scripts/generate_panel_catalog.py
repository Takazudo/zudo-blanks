#!/usr/bin/env python3
"""Refresh metadata without native tools; --images explicitly regenerates previews."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

import fnmatch
import hashlib

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "doc"
PANELS = ROOT / "panels"
PREVIEWS = SITE / "public/assets/panels"
GITHUB = "https://github.com/Takazudo/zudo-blanks/tree/main/panels/"
STACKS = {"art-spider-nest", "art-coral-vault", "art-fault-line", "art-kumiko-void", "art-woven-maze"}
SPECIAL = {"art-grouped-lowers", "art-strip-mine"}
COLOR = {
    "black": "#242833", "white": "#e8e7e2", "red": "#b84643", "green": "#508267",
    "blue": "#36799a", "purple": "#79639a", "yellow": "#c6a544",
}


def boards_for(directory: Path) -> list[Path]:
    name = directory.name
    if name in STACKS:
        return sorted(directory.glob("*L??*.kicad_pcb"))
    if name == "art-grouped-lowers":
        return sorted(directory.glob("lower-panel-*/*.kicad_pcb"))
    if name == "art-strip-mine":
        return sorted(directory.glob("pcb-*/strip-mine-*.kicad_pcb"))
    return sorted(directory.glob("*.kicad_pcb"))


def board_color(board: Path) -> str:
    match = re.search(r"(?:^|[-_])(black|white|red|green|blue|purple|yellow)(?:[-_.]|$)", board.as_posix())
    return COLOR[match.group(1)] if match else "#576c73"


def render_board(board: Path, kicad: str, height: int = 370) -> Image.Image:
    from PIL import Image
    with tempfile.TemporaryDirectory(prefix="panel-preview-") as temp:
        svg = Path(temp) / "board.svg"
        png = Path(temp) / "board.png"
        subprocess.run([
            kicad, "pcb", "export", "svg", "--mode-single", "--fit-page-to-board",
            "--exclude-drawing-sheet", "--layers", "F.Mask,F.Silkscreen,Edge.Cuts",
            "--output", str(svg), str(board),
        ], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["sips", "-s", "format", "png", "-Z", str(height), str(svg),
                        "--out", str(png)], check=True, stdout=subprocess.DEVNULL)
        artwork = Image.open(png).convert("RGBA")
        # KiCad plots transparent layer geometry. Color is a visual aid, not a CAM proof.
        base = Image.new("RGBA", artwork.size, board_color(board))
        return Image.alpha_composite(base, artwork).convert("RGB")


def panel_preview(name: str, boards: list[Path], kicad: str) -> Image.Image:
    from PIL import Image, ImageDraw
    if name in STACKS or name in SPECIAL:
        columns = 3 if len(boards) < 8 else 4
        cell_w, cell_h, margin = 240, 300, 20
        rows = (len(boards) + columns - 1) // columns
        sheet = Image.new("RGB", (columns * cell_w + margin * 2, rows * cell_h + margin * 2), "#f4f3ef")
        draw = ImageDraw.Draw(sheet)
        for index, board in enumerate(boards):
            image = render_board(board, kicad, 250)
            image.thumbnail((cell_w - 20, 255), Image.Resampling.LANCZOS)
            x = margin + (index % columns) * cell_w + (cell_w - image.width) // 2
            y = margin + (index // columns) * cell_h
            sheet.paste(image, (x, y))
            label = re.search(r"L\d\d", board.stem)
            title = label.group() if label else board.parent.name.replace("lower-panel-", "").replace("pcb-", "")
            draw.text((margin + (index % columns) * cell_w + 8, y + 262), title, fill="#30343b")
        return sheet
    image = render_board(boards[0], kicad)
    canvas = Image.new("RGB", (500, 430), "#f4f3ef")
    image.thumbnail((450, 385), Image.Resampling.LANCZOS)
    canvas.paste(image, ((500 - image.width) // 2, (430 - image.height) // 2))
    return canvas


DOCS = SITE / "src/content/docs"
START = "{/* BEGIN GENERATED INVENTORY */}"
END = "{/* END GENERATED INVENTORY */}"


def family_for(name: str, families: list[dict]) -> str:
    if name == "art-grouped-lowers":
        return "manufacturing/grouped-lowers"
    matches = [entry for entry in families if any(fnmatch.fnmatchcase(name, pattern) for pattern in entry["patterns"])]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one family for {name}, got {len(matches)}")
    return "panels/" + matches[0]["slug"]


def board_role(board: Path) -> str:
    parts = board.relative_to(PANELS).parts
    if "alternatives" in parts:
        return "reference alternative"
    if "fixture" in parts or "test" in parts:
        return "test input"
    if parts[0] == "art-grouped-lowers" or (parts[0] == "art-strip-mine" and parts[1].startswith("panel-")):
        return "fabrication sheet"
    if parts[0] in STACKS or parts[0] == "art-strip-mine":
        return "layer source"
    return "panel source"


def native_board_paths(directory: Path) -> list[Path]:
    # KiCad writes gitignored `.history` copies beside native boards. They are not panel sources.
    return sorted(board for board in directory.rglob("*.kicad_pcb") if ".history" not in board.parts)


def inventory() -> list[dict]:
    families = json.loads((SITE / "data/panel-pages.json").read_text())
    records = []
    for directory in sorted(path for path in PANELS.iterdir() if path.is_dir()):
        boards = native_board_paths(directory)
        if not boards:
            raise ValueError(f"No native boards in {directory}")
        name = directory.name
        records.append({"directory": name, "family": family_for(name, families),
                        "preview": f"assets/panels/{name}.png",
                        "boards": [{"path": str(board.relative_to(ROOT)), "role": board_role(board), "sha256": hashlib.sha256(board.read_bytes()).hexdigest()} for board in boards]})
    return records


def block(records: list[dict]) -> str:
    lines = [START, "", "## Variants and native file roles", "",
             "Widths in project names are nominal labels. Dimensions, finishes and manufacturing status must be read from the native source and project evidence.", "",
             "| Variant | Native files | File roles |", "| --- | ---: | --- |"]
    for record in records:
        name = record["directory"]
        roles = ", ".join(sorted({board["role"] for board in record["boards"]}))
        lines.append(f'| [{name}](#{name}) | {len(record["boards"])} | {roles} |')
    lines.append("")
    for record in records:
        name = record["directory"]
        lines += [f'<h3 id="{name}">{name}</h3>', "",
                  f'<img class="design-preview" src="/{record["preview"]}" alt="Native KiCad preview of {name}" loading="lazy" />', "",
                  f'[Project directory]({GITHUB}{name})', "", "| Native file | Role |", "| --- | --- |"]
        for board in record["boards"]:
            lines.append(f'| [{Path(board["path"]).name}](https://github.com/Takazudo/zudo-blanks/blob/main/{board["path"]}) | {board["role"]} |')
        lines.append("")
    return "\n".join(lines + [END])


def catalog(records: list[dict]) -> str:
    families = json.loads((SITE / "data/panel-pages.json").read_text())
    lines = [START, "", f'{len(records)} panel directories contain {sum(len(r["boards"]) for r in records)} native board files. The 19 family pages preserve every width, revision and alternative. Fabrication sheets and test inputs are counted as files, not additional designs. Frozen archive copies are outside this inventory.', "", '<div class="panel-grid">']
    for family in families:
        members = [r for r in records if r["family"] == "panels/" + family["slug"]]
        representative = members[0]
        url = "/docs/panels/" + family["slug"] + "/"
        lines += ['<article class="panel-card">', f'<a href="{url}"><img src="/{representative["preview"]}" alt="{family["title"]}" loading="lazy" /></a>',
                  f'<h3><a href="{url}">{family["title"]}</a></h3>', f'<p>{len(members)} project variants</p>', '</article>']
    lines += ['</div>', '', '[Grouped lower fabrication sheets](/docs/manufacturing/grouped-lowers/) are documented under Manufacturing.', '', END]
    return "\n".join(lines)


def generated_outputs(records: list[dict]) -> dict[Path, str]:
    outputs = {SITE / "data/panel-inventory.json": json.dumps(records, indent=2) + "\n"}
    pages = {record["family"] for record in records}
    for page in pages | {"panels/index"}:
        path = DOCS / (page + ".mdx")
        source = path.read_text()
        if source.count(START) != 1 or source.count(END) != 1:
            raise ValueError(f"Exactly one generated block required: {path}")
        content = catalog(records) if page == "panels/index" else block([r for r in records if r["family"] == page])
        outputs[path] = source[:source.index(START)] + content + source[source.index(END) + len(END):]
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check metadata/page drift without writing")
    parser.add_argument("--images", action="store_true", help="Explicitly run native image generation (KiCad, Pillow, sips)")
    parser.add_argument("--kicad-cli", default="kicad-cli")
    parser.add_argument("--only", nargs="*", help="Select preview directories; requires --images")
    args = parser.parse_args()
    if args.only is not None and not args.images:
        parser.error("--only requires --images; metadata always covers all directories")
    records = inventory()
    outputs = generated_outputs(records)
    drift = [str(path.relative_to(ROOT)) for path, content in outputs.items() if not path.exists() or path.read_text() != content]
    if args.check:
        if args.images:
            parser.error("--check and --images cannot be combined")
        if drift:
            raise SystemExit("Generated output drift: " + ", ".join(drift))
    else:
        for path, content in outputs.items():
            path.write_text(content)
    if args.images:
        selected = set(args.only) if args.only is not None else {r["directory"] for r in records}
        unknown = selected - {r["directory"] for r in records}
        if unknown:
            raise SystemExit(f"Unknown panel directories: {sorted(unknown)}")
        for name in sorted(selected):
            image = panel_preview(name, boards_for(PANELS / name), args.kicad_cli)
            image.save(PREVIEWS / f"{name}.png", optimize=True)
    print(f"Metadata {'checked' if args.check else 'generated'}: {len(records)} directories, {sum(len(r['boards']) for r in records)} native files")


if __name__ == "__main__":
    main()
