#!/usr/bin/env python3
"""Verify the frozen completed order subset against original run bytes and accounting."""
import argparse
import json
from pathlib import Path
import tempfile

from order_packages import sha, verify_bundle
from retain_order_bundle import restore, local_editor_state

SOURCE = '27481603195bb1318a0086d119294a5725dd36a0'
RUN = '37833323671'
DEFAULT = Path(__file__).resolve().parents[3] / 'order-packages/four-art-series/ordered'


def verify_ordered(snapshot=DEFAULT):
    snapshot = Path(snapshot)
    manifest = json.loads((snapshot / 'retention.json').read_text())
    if manifest.get('selection') != 'completed-split-red-25' or manifest['sourceCommit'] != SOURCE or manifest['runId'] != RUN:
        raise ValueError('Completed order identity differs')
    original_path = snapshot / 'provenance/original-SHA256SUMS'
    if sha(original_path) != manifest['originalChecksumSha256']:
        raise ValueError('Original checksum provenance differs')
    original = dict((rel, digest) for digest, rel in
                    (line.split('  ', 1) for line in original_path.read_text().splitlines()))
    for rel, entry in manifest['files'].items():
        if rel != 'SHA256SUMS' and original.get(rel) != entry['sha256']:
            raise ValueError(f'Retained file differs from original run: {rel}')
    # Only the subset inventory is new. Receipt, profile, source, DRC and CAM stay original.
    with tempfile.TemporaryDirectory(prefix='completed-art-order-') as tmp:
        root = Path(tmp)
        restore(snapshot, root)
        result = verify_bundle(root, SOURCE, RUN, selected_variants=['split-red'])
        order = json.loads((root / 'variants/split-red/order.json').read_text())
        if (order['selectedBoardCount'] != 34 or order['packageCount'] != 13
                or order['usefulBoardCount'] != 850 or order['orderedSheetsAndStandaloneUnits'] != 325
                or set(order['demandByBoardId'].values()) != {25}
                or any(p['quantity'] != 25 for p in order['packages'])):
            raise ValueError('Completed order quantity differs')
        completion = json.loads((snapshot / 'completion.json').read_text())
        zip_paths = {p.relative_to(root).as_posix() for p in root.rglob('*.zip')}
        if zip_paths != {p['zip']['path'] for p in order['packages']}:
            raise ValueError('Archive contains abandoned or missing order ZIPs')
        if {p.name for p in (root / 'variants').iterdir()} != {'split-red'}:
            raise ValueError('Archive contains abandoned alternatives')
        expected = [{'id': p['id'], 'quantity': p['quantity'], **p['zip']} for p in order['packages']]
        if completion['packages'] != expected:
            raise ValueError('Completed cart differs from verified packages')
        if result != manifest['verification']:
            raise ValueError('Completed subset verification differs')
    # Metadata/indexes also have a physical-file checksum inventory.
    sums = dict((rel, digest) for digest, rel in
                (line.split('  ', 1) for line in (snapshot / 'SHA256SUMS').read_text().splitlines()))
    actual = {p.relative_to(snapshot).as_posix() for p in snapshot.rglob('*')
              if p.is_file() and not local_editor_state(p) and p != snapshot / 'SHA256SUMS'}
    if actual != set(sums) or any(sha(snapshot / rel) != digest for rel, digest in sums.items()):
        raise ValueError('Physical completed order inventory differs')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', nargs='?', type=Path, default=DEFAULT)
    print(json.dumps(verify_ordered(parser.parse_args().snapshot), indent=2))
