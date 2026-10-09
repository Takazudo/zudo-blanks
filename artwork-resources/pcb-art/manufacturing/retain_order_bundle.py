#!/usr/bin/env python3
"""Store a verified order bundle in ordinary Git; restore duplicate CAM for checks."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

from order_packages import safe_path, sha, verify_bundle

def local_editor_state(path):
    return (path.suffix in ('.kicad_prl', '.lck') or path.name == '.DS_Store'
            or path.name.startswith('_autosave-')
            or any(part.endswith('-backups') for part in path.parts))


MAX_GIT_FILE = 95 * 1024 * 1024  # Leave margin below GitHub's 100 MiB hard limit.


def zip_members(bundle):
    """Index only flat, unique, regular entries in the verified order ZIPs."""
    result = {}
    for path in sorted(bundle.rglob('*.zip')):
        rel = path.relative_to(bundle).as_posix()
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError('Duplicate ZIP members')
            for info in archive.infolist():
                if info.is_dir() or Path(info.filename).name != info.filename:
                    raise ValueError('Unsafe ZIP member')
                data = archive.read(info)
                result.setdefault(hashlib.sha256(data).hexdigest(), {'zip': rel, 'member': info.filename})
    return result


def restore(snapshot, destination):
    snapshot = snapshot.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Restore destination must be empty')
    manifest = json.loads((snapshot / 'retention.json').read_text())
    if manifest['schemaVersion'] != 1:
        raise ValueError('Unsupported retention schema')
    bundle = snapshot / 'bundle'
    stored = {p.relative_to(bundle).as_posix() for p in bundle.rglob('*') if p.is_file() and not local_editor_state(p)}
    expected = {rel for rel, entry in manifest['files'].items() if 'zip' not in entry and 'base64' not in entry}
    if stored != expected:
        raise ValueError('Stored file inventory mismatch')
    for rel, entry in manifest['files'].items():
        dest = safe_path(destination, rel)
        if 'base64' in entry:
            data = base64.b64decode(entry['base64'], validate=True)
        elif 'zip' in entry:
            archive_path = safe_path(bundle, entry['zip'])
            member = entry['member']
            if Path(member).name != member or not member:
                raise ValueError('Unsafe ZIP member')
            with zipfile.ZipFile(archive_path) as archive:
                if archive.namelist().count(member) != 1:
                    raise ValueError('Missing or duplicate ZIP member')
                data = archive.read(member)
        else:
            source = safe_path(bundle, rel)
            if source.stat().st_size >= MAX_GIT_FILE:
                raise ValueError(f'File exceeds Git storage limit: {rel}')
            data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry['sha256'] or len(data) != entry['bytes']:
            raise ValueError(f'Restored bytes mismatch: {rel}')
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return manifest


def verify_saved(snapshot, expected_source=None, expected_run_id=None):
    with tempfile.TemporaryDirectory(prefix='art-order-restore-') as tmp:
        root = Path(tmp)
        manifest = restore(snapshot, root)
        result = verify_bundle(root, expected_source or manifest['sourceCommit'],
                               expected_run_id or manifest['runId'])
        if result != manifest['verification']:
            raise ValueError('Saved verification receipt differs')
        return result


def write_navigation(destination):
    bundle = destination / 'bundle'
    for variant in ('individual', 'grouped', 'split-red'):
        order = json.loads((bundle / 'variants' / variant / 'order.json').read_text())
        individual = {b['id']: b for b in json.loads((bundle / 'individual-verification.json').read_text())}
        rows = [f'# Open {variant}', '',
                f'[Order quantities and settings](bundle/variants/{variant}/ORDER.md) · [All alternatives](README.md)', '',
                'Choose only one alternative. Open PCB files in KiCad PCB Editor; upload the listed ZIPs to JLCPCB.', '',
                '| Package | Color / finish | KiCad PCB | CAM preview | Order ZIP |',
                '| --- | --- | --- | --- | --- |']
        for item in order['packages']:
            name = item['id']
            if item['kind'] == 'scored_lower_grid':
                pcb = f'variants/{variant}/native/{name}/{name}.kicad_pcb'
                preview = f'variants/{variant}/{name}.png'
            else:
                pcb = individual[name]['nativeBoard']
                preview = individual[name]['preview']
            paths = [pcb, preview, item['zip']['path']]
            for path in paths:
                if not safe_path(bundle, path).is_file():
                    raise ValueError(f'Broken navigation target: {path}')
            links = [f'[{label}](bundle/{path})' for label, path in zip(('PCB', 'Preview', 'ZIP'), paths)]
            rows.append(f"| {name} | {item['color']} / {item['finish']} | " + ' | '.join(links) + ' |')
        (destination / f'OPEN-{variant}.md').write_text('\n'.join(rows) + '\n')
    receipt = json.loads((destination / 'retention.json').read_text())
    (destination / 'README.md').write_text(f'''# Four-series saved order candidates

Open the boards directly in KiCad PCB Editor, with their adjacent `.kicad_pro` files. No artifact download, Docker, or generation is needed to inspect this snapshot.

| Alternative | Direct PCB / preview / ZIP links | Purchase list | Order lines |
| --- | --- | --- | ---: |
| Individual: all 34 boards separate | [Open individual](OPEN-individual.md) | [ORDER](bundle/variants/individual/ORDER.md) | 34 |
| Grouped: red ten, 3 × 4 with two blank cells | [Open grouped](OPEN-grouped.md) | [ORDER](bundle/variants/grouped/ORDER.md) | 12 |
| Split-red: six plus four, no blank cells | [Open split-red](OPEN-split-red.md) | [ORDER](bundle/variants/split-red/ORDER.md) | 13 |

Coral Vault, Fault Line, Kumiko Void **wide**, and Spider Nest: 34 original boards, four standalone tops and 30 lowers. Strip Mine, Woven Maze and standard Kumiko are excluded. Groups match **both color and finish**; black ENIG and black lead-free HASL are separate. Purple/yellow/blue lowers remain standalone. The six-red sheet contains Spider L08, Coral L05/L07 and Kumiko L02/L05/L08; the four-red sheet contains Fault L02/L04/L06/L08.

Each alternative supplies 25 stacks per series. Choose **one** purchase list, never every ZIP in this directory. [Quote comparison](bundle/QUOTE-COMPARISON.md) · [Nominal stack sides](bundle/previews/nominal-stack-sides.png). Prices are unknown; local verification is not factory CAM/scoring approval or physical-fit confirmation. Existing FR-4, 1.6 mm, two copper layers, 1 oz, routing, scores and finish conditions are unchanged.

## Provenance and storage

- Original run: https://github.com/Takazudo/zudo-blanks/actions/runs/{receipt['runId']}
- Tested source commit: `{receipt['sourceCommit']}` (the tested PR merge, not the later main merge).
- [Original receipt](bundle/receipt.json), [original checksum inventory](bundle/SHA256SUMS), [retention mapping](retention.json).
- All 34 source boards/projects, both grouped native alternatives, order ZIPs, previews, settings and verification evidence remain in ordinary Git. No LFS or outer artifact ZIP.
- Original disposable KiCad local settings are encoded in the retention mapping, so opening a PCB does not modify tracked window settings. New local editor state and backups are ignored. Duplicate raw CAM bytes are restored from the unchanged order ZIPs for verification. `bundle/SHA256SUMS` describes the **restored full bundle**, not just the retained physical files. Every restored byte must match it. No native geometry or order ZIP is regenerated during retention.
- Stored bundle: {receipt['storedBytes']:,} bytes in {receipt['storedFiles']} files; original bundle: {receipt['originalBytes']:,} bytes. Largest retained file: {receipt['largestFileBytes']:,} bytes.

See [the storage/update procedure](../../../scripts/art-order/README.md#ordinary-git-storage) for verification and replacement. Treat this as a frozen snapshot until a newly verified bundle is explicitly retained and reviewed.
''')


def retain(bundle, destination, expected_source, expected_run_id):
    verification = verify_bundle(bundle, expected_source, expected_run_id)
    if verification['variants'] != ['individual', 'grouped', 'split-red']:
        raise ValueError('Retain all three alternatives together')
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Use a fresh empty retention destination')
    members = zip_members(bundle)
    entries = {}
    stored_bytes = stored_files = original_bytes = largest = 0
    for source in sorted(bundle.rglob('*')):
        if not source.is_file():
            continue
        rel = source.relative_to(bundle).as_posix()
        safe_path(bundle, rel)
        digest, size = sha(source), source.stat().st_size
        entry = {'sha256': digest, 'bytes': size}
        # Keep the native files, order packages and previews directly accessible.
        # Remove only raw CAM duplicates; unusual auxiliary outputs remain intact.
        if source.suffix == '.kicad_prl':
            entry['base64'] = base64.b64encode(source.read_bytes()).decode('ascii')
        elif '/cam/' in rel and source.suffix != '.zip' and digest in members:
            entry.update(members[digest])
        else:
            if size >= MAX_GIT_FILE:
                raise ValueError(f'File exceeds Git storage limit: {rel}')
            dest = safe_path(destination / 'bundle', rel)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
            stored_bytes += size
            stored_files += 1
            largest = max(largest, size)
        entries[rel] = entry
        original_bytes += size
    manifest = {'schemaVersion': 1, 'sourceCommit': expected_source, 'runId': str(expected_run_id),
                'verification': verification, 'storedBytes': stored_bytes, 'storedFiles': stored_files,
                'originalBytes': original_bytes, 'largestFileBytes': largest, 'files': entries}
    (destination / 'retention.json').write_text(json.dumps(manifest, indent=2) + '\n')
    write_navigation(destination)
    return verify_saved(destination, expected_source, expected_run_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--retain', type=Path, help='Full verified bundle to retain')
    mode.add_argument('--verify-saved', type=Path, help='Retained snapshot to reconstruct and verify')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--expected-source', required=True)
    parser.add_argument('--expected-run-id', required=True)
    args = parser.parse_args()
    if args.retain:
        if not args.output:
            parser.error('--retain requires --output')
        result = retain(args.retain.resolve(), args.output.resolve(), args.expected_source, args.expected_run_id)
    else:
        result = verify_saved(args.verify_saved, args.expected_source, args.expected_run_id)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
