#!/usr/bin/env python3
"""Verify the committed PCB art import without requiring its original bundle."""
from __future__ import annotations
import argparse
import csv
from collections import Counter
import hashlib
import json
from pathlib import Path

ART_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ART_ROOT.parents[1]
IMPORT_MANIFEST = ART_ROOT / 'IMPORT_MANIFEST.json'
EXPECTED_BUNDLE_LIST_SHA256 = '268e1c329f94d2fa55d3641e0ca32b8698e8117ac91bc8dadb58263f643d39d8'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        digest, separator, name = line.partition('  ')
        if not separator:
            raise ValueError(f'Invalid checksum line: {line}')
        result[name] = digest
    return result


def fail(message: str) -> None:
    raise SystemExit(f'Import verification failed: {message}')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path,
                        help='Optional original handoff directory; verifies all 944 intake hashes.')
    args = parser.parse_args()

    manifest = json.loads(IMPORT_MANIFEST.read_text(encoding='utf-8'))
    source_manifest_path = ART_ROOT / 'SOURCE_RESOURCE_MANIFEST.json'
    checksum_list_path = ART_ROOT / 'SOURCE_SHA256SUMS.txt'
    if sha256(checksum_list_path) != EXPECTED_BUNDLE_LIST_SHA256:
        fail('archived source checksum list does not match the recorded intake digest')
    inventory = json.loads(source_manifest_path.read_text(encoding='utf-8'))
    source_files = inventory['files']
    files = manifest['files']
    if len(source_files) != 944 or len(files) != 944:
        fail(f'expected 944 source entries, found inventory={len(source_files)} import={len(files)}')

    expected_hashes = {item['path']: item['sha256'] for item in source_files}
    checksums = source_hashes(checksum_list_path)
    if checksums != expected_hashes:
        fail('archived SHA256SUMS.txt and RESOURCE_MANIFEST.json list different source hashes')

    provenance = manifest['sourceBundle']
    if provenance['sha256SumsFileSha256'] != EXPECTED_BUNDLE_LIST_SHA256:
        fail('import manifest records a different checksum-list digest')
    if provenance['resourceManifestRepositorySha256'] != sha256(source_manifest_path):
        fail('archived source resource manifest changed')
    source_root = args.source_root.resolve() if args.source_root else None
    if source_root:
        original_inventory = source_root / provenance['resourceManifestOriginalPath']
        original_checksum_list = source_root / provenance['sha256SumsFileOriginalPath']
        if not original_inventory.is_file() or sha256(original_inventory) != provenance['resourceManifestSourceSha256']:
            fail('original source resource manifest differs from the recorded intake checksum')
        if not original_checksum_list.is_file() or sha256(original_checksum_list) != EXPECTED_BUNDLE_LIST_SHA256:
            fail('original SHA256SUMS.txt differs from the recorded intake checksum')

    actual_source_paths = {entry['originalPath'] for entry in files}
    if actual_source_paths != set(expected_hashes):
        fail('import manifest does not account for every original source path exactly once')
    expected_unique_paths = {item.get('repositoryPath') for item in files if item.get('repositoryPath')}
    if manifest.get('uniqueRepositoryPaths') != len(expected_unique_paths):
        fail('unique repository path count differs from the mapped file records')

    verified_repo_paths: set[str] = set()
    status_counts: Counter[str] = Counter()
    source_sizes = {item['path']: item['bytes'] for item in source_files}
    for item in files:
        original = item['originalPath']
        if item['sourceSha256'] != expected_hashes[original]:
            fail(f'{original}: source checksum differs from the incoming inventory')
        if item['sourceBytes'] != source_sizes[original]:
            fail(f'{original}: source byte size differs from the incoming inventory')
        status_counts[item['status']] += 1
        repository_path = item.get('repositoryPath')
        if repository_path:
            path = REPO_ROOT / repository_path
            if not path.is_file():
                fail(f'{original}: mapped repository file is missing: {repository_path}')
            if item.get('repositorySha256') != sha256(path):
                fail(f'{original}: mapped repository file checksum changed: {repository_path}')
            if item.get('repositoryBytes') != path.stat().st_size:
                fail(f'{original}: mapped repository file size changed: {repository_path}')
            verified_repo_paths.add(repository_path)
        elif item['status'].startswith('omitted_'):
            regeneration_path = item.get('regenerationPath')
            regeneration_command = item.get('regenerationCommand')
            if not regeneration_path or not regeneration_command:
                fail(f'{original}: omission has no explicit regeneration path and command')
            relative_path = Path(regeneration_path)
            if relative_path.is_absolute() or '..' in relative_path.parts:
                fail(f'{original}: regeneration path must be repository-relative')
            if item['status'] == 'omitted_generated_vector':
                expected_root = 'artwork-resources/pcb-art/generated/rev5-export/resources/vector/'
                expected_command = manifest['regeneration']['nativeExportCommandFromRepositoryRoot']
            else:
                expected_root = 'artwork-resources/pcb-art/preview-source/dist/'
                expected_command = manifest['regeneration']['previewCommandFromRepositoryRoot']
            if not regeneration_path.startswith(expected_root):
                fail(f'{original}: regeneration path is outside its generated output root')
            if regeneration_command != expected_command:
                fail(f'{original}: regeneration command differs from the documented generator')
        else:
            fail(f'{original}: missing repository path without an explicit omission reason')
        if source_root:
            source_path = source_root / original
            if not source_path.is_file():
                fail(f'{original}: source path is missing from the optional source root')
            if sha256(source_path) != item['sourceSha256']:
                fail(f'{original}: intake checksum differs at the optional source root')

    for artifact in manifest.get('createdArtifacts', []):
        path = REPO_ROOT / artifact['repositoryPath']
        if not path.is_file():
            fail(f'created import artifact is missing: {artifact["repositoryPath"]}')
        if sha256(path) != artifact['repositorySha256']:
            fail(f'created import artifact checksum changed: {artifact["repositoryPath"]}')
        if path.stat().st_size != artifact['repositoryBytes']:
            fail(f'created import artifact size changed: {artifact["repositoryPath"]}')

    if dict(sorted(status_counts.items())) != manifest.get('dispositionSummary'):
        fail('disposition summary differs from the source file records')
    if len(verified_repo_paths) != manifest.get('uniqueRepositoryPaths'):
        fail('unique repository path count differs from verified destinations')

    native_manifest_path = ART_ROOT / 'pcb/manifest.json'
    native_manifest = json.loads(native_manifest_path.read_text(encoding='utf-8'))
    boards = native_manifest['boards']
    if len(boards) != 52:
        fail(f'expected 52 original board IDs, found {len(boards)}')
    selected = [board for board in boards if board['category'] == 'selected']
    alternatives = [board for board in boards if board['category'] == 'alternatives']
    if len(selected) != 43 or len(alternatives) != 9:
        fail(f'expected 43 selected and 9 alternative boards; found {len(selected)} and {len(alternatives)}')
    if Counter(board['designId'] for board in selected) != {
        'spider-nest': 8, 'coral-vault': 8, 'fault-line': 9, 'kumiko-void': 9, 'woven-maze': 9
    }:
        fail('selected design/layer inventory does not match the five-design set')
    if Counter(board['designId'] for board in alternatives) != {'kumiko-void': 9}:
        fail('standard Kumiko alternative is not a complete nine-board set')
    if Counter(board['finish'] == 'mask-only' for board in selected) != {True: 32, False: 11}:
        fail('selected finish inventory is not 11 ENIG and 32 mask-only boards')
    expected_layers = {
        'spider-nest': [
            ('black', 'enig-art'), ('white', 'mask-only'), ('black', 'enig-fill'), ('white', 'mask-only'),
            ('black', 'enig-fill'), ('white', 'mask-only'), ('black', 'enig-fill'), ('red', 'mask-only'),
        ],
        'coral-vault': [
            ('black', 'enig-art'), ('green', 'mask-only'), ('purple', 'mask-only'), ('black', 'enig-fill'),
            ('red', 'mask-only'), ('yellow', 'mask-only'), ('red', 'mask-only'), ('blue', 'mask-only'),
        ],
        'fault-line': [
            ('black', 'enig-art'), ('red', 'mask-only'), ('black', 'mask-only'), ('red', 'mask-only'),
            ('black', 'mask-only'), ('red', 'mask-only'), ('black', 'mask-only'), ('red', 'mask-only'),
            ('black', 'mask-only'),
        ],
        'kumiko-void': [
            ('black', 'enig-art'), ('red', 'mask-only'), ('green', 'mask-only'), ('black', 'enig-art'),
            ('red', 'mask-only'), ('green', 'mask-only'), ('black', 'enig-art'), ('red', 'mask-only'),
            ('green', 'mask-only'),
        ],
        'woven-maze': [
            ('black', 'enig-art'), ('white', 'mask-only'), ('black', 'mask-only'), ('white', 'mask-only'),
            ('black', 'mask-only'), ('white', 'mask-only'), ('black', 'mask-only'), ('white', 'mask-only'),
            ('black', 'mask-only'),
        ],
    }
    for design_id, expected in expected_layers.items():
        design_boards = sorted(
            (board for board in selected if board['designId'] == design_id),
            key=lambda board: board['layerNumber'],
        )
        actual = [(board['maskColor'], board['finish']) for board in design_boards]
        if actual != expected:
            fail(f'{design_id}: layer, color, and finish metadata differ from Revision 5')
    alternative_layers = sorted(alternatives, key=lambda board: board['layerNumber'])
    if [(board['maskColor'], board['finish']) for board in alternative_layers] != expected_layers['kumiko-void']:
        fail('standard Kumiko color and finish sequence differs from the selected variant')

    source_to_repo = {item['originalPath']: item.get('repositoryPath') for item in files}
    for board in boards:
        if Path(board['nativeBoard']).stem != board['id']:
            fail(f'{board["id"]}: original board ID is not preserved in its filename')
        board_path = REPO_ROOT / board['nativeBoard']
        if not board_path.is_file():
            fail(f'{board["id"]}: native board path is missing')
        if sha256(board_path) != board['nativeBoardSha256']:
            fail(f'{board["id"]}: native board checksum differs from the manifest')
        if source_to_repo.get(board['sourceNativeBoard']) != board['nativeBoard']:
            fail(f'{board["id"]}: source board path does not map to its panel home')

    csv_path = ART_ROOT / 'pcb/manifest.csv'
    with csv_path.open(newline='', encoding='utf-8') as handle:
        csv_rows = list(csv.DictReader(handle))
    if len(csv_rows) != 52 or {row['id'] for row in csv_rows} != {board['id'] for board in boards}:
        fail('CSV board manifest does not match the JSON manifest')
    for row in csv_rows:
        board = next(item for item in boards if item['id'] == row['id'])
        for field in ['nativeBoard', 'sourceNativeBoard', 'layerNumber', 'maskColor', 'finish']:
            if str(row[field]) != str(board[field]):
                fail(f'{row["id"]}: CSV {field} differs from JSON')
    if source_root:
        original_native_manifest = json.loads(
            (source_root / 'pcb/manifest.json').read_text(encoding='utf-8')
        )
        original_by_id = {board['id']: board for board in original_native_manifest['boards']}
        if set(original_by_id) != {board['id'] for board in boards}:
            fail('imported native manifest does not retain the original board ID inventory')
        for board in boards:
            original = original_by_id[board['id']]
            for key, value in original.items():
                if key == 'nativeBoard':
                    if board['sourceNativeBoard'] != value:
                        fail(f'{board["id"]}: original nativeBoard provenance differs')
                elif board.get(key) != value:
                    fail(f'{board["id"]}: original {key} metadata differs')

    scan_suffixes = {'.md', '.mdx', '.py', '.js', '.mjs', '.json', '.csv', '.ts', '.txt'}
    for path in ART_ROOT.rglob('*'):
        if path.is_file() and path.suffix in scan_suffixes:
            raw = path.read_bytes()
            if b'/workspace/' + b'scratch/' in raw:
                fail(f'non-portable source-workspace path remains in {path.relative_to(REPO_ROOT)}')

    result = {
        'passed': True,
        'sourceFiles': len(files),
        'repositoryMappedEntries': sum(1 for item in files if item.get('repositoryPath')),
        'uniqueRepositoryPaths': len(verified_repo_paths),
        'explicitlyOmittedEntries': sum(1 for item in files if item['status'].startswith('omitted_')),
        'selectedBoards': len(selected),
        'alternativeBoards': len(alternatives),
        'selectedEnigBoards': sum(board['finish'] != 'mask-only' for board in selected),
        'selectedMaskOnlyBoards': sum(board['finish'] == 'mask-only' for board in selected),
        'originalSourceTreeChecked': bool(source_root),
        'statusCounts': dict(sorted(status_counts.items())),
    }
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
