#!/usr/bin/env python3
"""Stage browser assets from the repository's canonical PCB art sources."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "artwork-resources/pcb-art"
PUBLIC = ROOT / "doc/public/assets/pcb-art"
DESIGNS = {
    "spider-nest": "01-spider-nest-L01-black-enig-art.kicad_pcb",
    "coral-vault": "03-coral-vault-L01-black-enig-art.kicad_pcb",
    "fault-line": "13-fault-line-L01-black-enig-art.kicad_pcb",
    "kumiko-void": "17-kumiko-void-wide-L01-black-enig-art.kicad_pcb",
    "woven-maze": "18-woven-maze-L01-black-enig-art.kicad_pcb",
}


def clean_line_ends(value: str) -> str:
    """Remove export-only trailing spaces without changing line boundaries."""
    return re.sub(r"[ \t]+(?=\r?$)", "", value, flags=re.MULTILINE)


def copy_tree(source: Path, destination: Path, pattern: str) -> int:
    destination.mkdir(parents=True, exist_ok=True)
    files = sorted(source.glob(pattern))
    for path in files:
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    return len(files)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kicad-cli", default="kicad-cli")
    parser.add_argument("--without-vectors", action="store_true", help="Copy only existing art resources")
    args = parser.parse_args()
    images = copy_tree(SOURCE / "resources/images", PUBLIC / "images", "*.png")
    images += copy_tree(SOURCE / "resources/images", PUBLIC / "images", "*.svg")
    reviews = copy_tree(SOURCE / "resources/manufacturing-review", PUBLIC / "manufacturing-review", "*.png")
    reviews += copy_tree(SOURCE / "resources/manufacturing-review", PUBLIC / "manufacturing-review", "*.csv")
    comparisons = copy_tree(SOURCE / "manufacturing", PUBLIC / "cam-comparisons", "candidate-comparison-*.png")
    for name in ("native-cam-representative.png", "top-border-comparisons.png"):
        shutil.copyfile(SOURCE / "manufacturing" / name, PUBLIC / "cam-comparisons" / name)
        comparisons += 1
    # The viewer reads design and variant from URL queries or hashes. One offline file serves
    # all five designs and both Kumiko variants without six duplicate 1.9 MiB files.
    viewer = SOURCE / "preview-source/dist/index.html"
    previews_dir = PUBLIC / "previews"
    previews_dir.mkdir(parents=True, exist_ok=True)
    if not viewer.is_file():
        raise SystemExit(f"Generate the offline viewer first: {viewer}")
    (previews_dir / "index.html").write_text(clean_line_ends(viewer.read_text()))
    previews = 1
    vector_dir = PUBLIC / "vector"
    vector_dir.mkdir(parents=True, exist_ok=True)
    if not args.without_vectors:
        for name, filename in DESIGNS.items():
            board = ROOT / "panels" / f"art-{name}" / filename
            output = vector_dir / f"{name}-top-edge-cuts.svg"
            with tempfile.TemporaryDirectory(prefix="panel-vector-") as temp:
                temp_output = Path(temp) / "edges.svg"
                subprocess.run([args.kicad_cli, "pcb", "export", "svg", "--mode-single",
                                "--fit-page-to-board", "--exclude-drawing-sheet", "--layers", "Edge.Cuts",
                                "--output", str(temp_output), str(board)], check=True, stdout=subprocess.DEVNULL)
                svg = temp_output.read_text()
            # KiCad includes wall-clock export time in its title; omit it for reproducibility.
            start = svg.find("<title>")
            end = svg.find("</title>", start)
            if start < 0 or end < 0:
                raise RuntimeError(f"KiCad SVG title missing: {board}")
            svg = svg[:start] + f"<title>{name} top Edge.Cuts inspection vector</title>" + svg[end + 8:]
            output.write_text(clean_line_ends(svg))
    print(f"Staged {images} design images, {reviews} review files, {comparisons} CAM comparison images, {previews} interactive previews, {0 if args.without_vectors else len(DESIGNS)} top-edge vectors")


if __name__ == "__main__":
    main()
