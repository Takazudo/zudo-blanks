#!/usr/bin/env python3
"""Build the panel inventory and compact previews from committed KiCad boards."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

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


def category(name: str) -> str:
    if name.startswith("saucer"):
        return "Saucer series"
    if name.startswith("art-"):
        return "Artwork and layered designs"
    if name.startswith("zb-side"):
        return "Side frames"
    return "Plain blanks and adapters"


def label(name: str) -> str:
    if name.startswith("alumi-blanks-"):
        m = re.search(r"-(1U|3U)-(\d+)hp$", name)
        return f"Plain {m.group(1)} · {m.group(2)} HP" if m else name
    if name.startswith("saucer"):
        m = re.match(r"saucer(\d+)-(.+)-(\d+)hp", name)
        return f"Saucer {m.group(1)} · {m.group(2).replace('-', ' ').title()} · {m.group(3)} HP" if m else name
    return name.removeprefix("art-").replace("-", " ").title()


def status(name: str, count: int) -> str:
    if name in STACKS:
        return f"{count} selected layers · local native DRC/CAM checked · factory review pending"
    if name == "art-grouped-lowers":
        return f"{count} grouped sheets · local native DRC/CAM checked · factory review pending"
    if name == "art-strip-mine":
        return f"{count} layered source boards · historical project status"
    return "Repository design · manufacturing status not established"


def build_mdx(records: list[dict]) -> str:
    lines = ["---", "title: Panel Catalog", "description: Every panel project in the repository, with a source-derived preview.", "sidebar_position: 1", "---", "",
             f"Browse all {len(records)} panel project directories. Each image is a **KiCad layer rendering** of the committed board source. It is a visual directory aid, not a supplier CAM approval. The five new layered designs and grouped lower packages show every selected board or sheet; open their design pages for the Revision 5 visual concept, interactive 3D preview and fabrication records.", "",
             "**Release boundary:** Local native DRC and CAM checks cover the five new stacks and grouped lower sheets. Factory CAM review, quotes, finish availability and physical fit remain pending. No purchase or factory acceptance is recorded.", "",
             "[Five layered designs](../designs/) · [Manufacturing records](../manufacturing/) · [Preview regeneration](../workflow/panel-previews)", ""]
    for group in ["Plain blanks and adapters", "Side frames", "Artwork and layered designs", "Saucer series"]:
        items = [r for r in records if r["category"] == group]
        lines.extend([f"## {group}", "", f"{len(items)} project directories.", "", '<div className="panel-grid">'])
        for r in items:
            lines.extend([
                '<article className="panel-card">',
                f'<a href="{GITHUB}{r["directory"]}"><img src="/assets/panels/{r["directory"]}.png" alt="KiCad source rendering of {r["label"]}" loading="lazy" /></a>',
                f'<h3><a href="{GITHUB}{r["directory"]}">{r["label"]}</a></h3>',
                f'<p>{r["status"]}</p>',
                f'<small><code>panels/{r["directory"]}</code></small>',
                '</article>',
            ])
        lines.extend(["</div>", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kicad-cli", default="kicad-cli")
    parser.add_argument("--only", nargs="*", help="Regenerate named panel previews only")
    args = parser.parse_args()
    dirs = sorted(path for path in PANELS.iterdir() if path.is_dir())
    records = []
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    for directory in dirs:
        boards = boards_for(directory)
        if not boards:
            raise SystemExit(f"No board source in {directory}")
        name = directory.name
        record = {"directory": name, "category": category(name), "label": label(name),
                  "status": status(name, len(boards)), "boards": [str(p.relative_to(ROOT)) for p in boards],
                  "preview": f"assets/panels/{name}.png"}
        records.append(record)
        if args.only is None or name in args.only:
            image = panel_preview(name, boards, args.kicad_cli)
            output = PREVIEWS / f"{name}.png"
            image.save(output, optimize=True)
            print(f"{name}: {len(boards)} boards, {output.stat().st_size:,} bytes", flush=True)
    if args.only is not None:
        unknown = set(args.only) - {r["directory"] for r in records}
        if unknown:
            raise SystemExit(f"Unknown panels: {sorted(unknown)}")
    (SITE / "src/content/docs/catalog/index.mdx").write_text(build_mdx(records))
    inventory = SITE / "data/panel-inventory.json"
    inventory.parent.mkdir(parents=True, exist_ok=True)
    inventory.write_text(json.dumps(records, indent=2) + "\n")


if __name__ == "__main__":
    main()
