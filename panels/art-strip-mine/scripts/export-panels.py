"""Export combined panels and copper-free blue board; verify ZIP payloads."""
import os
from pathlib import Path
import subprocess
from zipfile import ZipFile, ZIP_DEFLATED
root = Path(__file__).resolve().parent.parent
cli = os.environ.get("KICAD_CLI", "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
layers = "F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts"
for folder in ["panel-black", "panel-red", "pcb-09-blue"]:
    directory = root / folder
    pcb, = directory.glob("*.kicad_pcb")
    out = directory / "gerber"
    out.mkdir(exist_ok=True)
    # Remove only previous generated exports, preventing stale PTH drill files.
    for f in out.iterdir():
        if f.suffix in {".gtl", ".gbl", ".gts", ".gbs", ".gto", ".gbo", ".gm1", ".gbr", ".gbrjob", ".drl"}:
            f.unlink()
    panel = folder.startswith("panel-")
    subprocess.run([cli, "pcb", "export", "gerbers", "--layers", layers + (",Dwgs.User" if panel else ""),
                    "-o", str(out) + "/", str(pcb)], check=True)
    subprocess.run([cli, "pcb", "export", "drill", "--format", "excellon", "-o", str(out) + "/", str(pcb)], check=True)
    files = list(out.iterdir())
    if panel:
        files += [directory / "FABRICATION.txt"]
    archive = directory / (pcb.stem + "-gerbers.zip")
    with ZipFile(archive, "w", ZIP_DEFLATED) as z:
        for f in sorted(files):
            z.write(f, f.name)
    with ZipFile(archive) as z:
        assert z.testzip() is None
        assert all(z.read(f.name) == f.read_bytes() for f in files)
    print(archive)
