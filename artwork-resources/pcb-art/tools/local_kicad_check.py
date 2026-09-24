#!/usr/bin/env python3
"""Locally run native KiCad DRC and optionally generate CAM review output.

This standard-library-only helper was prepared here but KiCad itself was not
available here. Commands are based on the official KiCad 8 CLI documentation:
https://docs.kicad.org/8.0/en/cli/cli.html

It never rewrites source boards, never suppresses violations, and never calls
an output a manufacturing release. Review Gerbers and drills in a CAM viewer.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]
MAC_CLI = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'


def commands(cli, board, target, export_cam):
    drc = [cli, 'pcb', 'drc', '--format', 'json', '--units', 'mm',
           '--severity-all', '--exit-code-violations', '--output', str(target/'drc.json'), str(board)]
    items = [('drc', drc)]
    if export_cam:
        items += [
          ('gerbers', [cli, 'pcb', 'export', 'gerbers', '--layers', 'F.Cu,B.Cu,F.Mask,B.Mask,Edge.Cuts',
                       '--precision', '6', '--output', str(target/'cam')+'/', str(board)]),
          ('drill', [cli, 'pcb', 'export', 'drill', '--format', 'excellon',
                     '--drill-origin', 'absolute', '--excellon-units', 'mm',
                     '--excellon-oval-format', 'route', '--excellon-separate-th',
                     '--generate-map', '--map-format', 'svg',
                     '--output', str(target/'cam')+'/', str(board)]),
        ]
    return items


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest', type=Path, default=ROOT/'pcb'/'manifest.json')
    ap.add_argument('--boards-root', type=Path, default=REPO_ROOT,
                    help='Repository root containing the panel homes, or a local edited copy.')
    ap.add_argument('--output', type=Path, required=True, help='New empty output directory; existing contents are never overwritten')
    ap.add_argument('--category', choices=['selected','alternatives','all'], default='selected')
    ap.add_argument('--design', help='Optional designId filter, e.g. spider-nest')
    ap.add_argument('--kicad-cli', help='Path to KiCad CLI; macOS app path is detected automatically')
    ap.add_argument('--export-cam', action='store_true', help='Also plot Gerbers and separated NPTH drills for visual CAM review, including boards with DRC violations')
    ap.add_argument('--plan', action='store_true', help='Print exact commands without running KiCad or writing anything')
    args = ap.parse_args()
    manifest = json.loads(args.manifest.read_text())
    selected = [b for b in manifest['boards'] if (args.category=='all' or b['category']==args.category)
                and (not args.design or b['designId']==args.design)]
    if not selected:
        ap.error('No boards match the filter')
    cli = args.kicad_cli or shutil.which('kicad-cli') or (MAC_CLI if Path(MAC_CLI).is_file() else None)
    if not cli and not args.plan:
        raise SystemExit('KiCad CLI was not found. Install KiCad 8+ locally or pass --kicad-cli /path/to/kicad-cli. No checks were run.')
    if args.output.exists() and any(args.output.iterdir()) and not args.plan:
        raise SystemExit('Output directory is not empty. Choose a new --output directory to preserve previous evidence.')
    for b in selected:
        if not (args.boards_root/b['nativeBoard']).is_file():
            raise SystemExit(f'Missing native board: {args.boards_root/b["nativeBoard"]}')
    jobs = []
    for b in selected:
        board = (args.boards_root/b['nativeBoard']).resolve()
        target = (args.output/b['id']).resolve()
        jobs.append((b, board, target, commands(cli or 'kicad-cli', board, target, args.export_cam)))
    if args.plan:
        print(json.dumps([{'id': b['id'], 'commands':[{'purpose':name,'argv':argv} for name,argv in cmd]}
                          for b,board,target,cmd in jobs], indent=2))
        return
    version = subprocess.run([cli, 'version'], text=True, capture_output=True)
    if version.returncode:
        raise SystemExit(f'Could not read KiCad version: {version.stderr}')
    # Ask the installed tool for help too: an unsupported option must fail
    # explicitly rather than silently falling back to a different CAM mode.
    help_commands = [['pcb','drc'], ['pcb','export','gerbers'], ['pcb','export','drill']] if args.export_cam else [['pcb','drc']]
    help_text={}
    for command in help_commands:
        r=subprocess.run([cli,*command,'--help'],text=True,capture_output=True)
        if r.returncode:
            raise SystemExit(f'Installed KiCad does not support {command}: {r.stderr}')
        help_text[' '.join(command)]=r.stdout+r.stderr
    args.output.mkdir(parents=True, exist_ok=True)
    results=[]
    report={'startedUtc':datetime.now(timezone.utc).isoformat(), 'kicadVersion':version.stdout.strip(),
            'nativeKiCadActuallyRun':True, 'category':args.category,
            'inputManifest':str(args.manifest.resolve()),
            'inputManifestSha256':hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
            'camIsReviewOnly':True, 'manufacturingRelease':False, 'boards':results}
    (args.output/'installed-cli-help.json').write_text(json.dumps(help_text,indent=2))
    for b, board, target, cmds in jobs:
        target.mkdir(parents=True)
        if args.export_cam:
            (target/'cam').mkdir()
        record={'id':b['id'],'board':str(board),'inputSha256':hashlib.sha256(board.read_bytes()).hexdigest(),'commands':[]}
        fatal=False
        for name, argv in cmds:
            r=subprocess.run(argv,text=True,capture_output=True)
            (target/(name+'.stdout.txt')).write_text(r.stdout)
            (target/(name+'.stderr.txt')).write_text(r.stderr)
            record['commands'].append({'purpose':name,'argv':argv,'exitCode':r.returncode})
            if name=='drc':
                record['drcViolationsReported']=r.returncode==5
                record['drcReportCreated']=(target/'drc.json').is_file()
                fatal=r.returncode not in (0,5) or not record['drcReportCreated']
            elif r.returncode:
                fatal=True
            if fatal:
                break
        record['commandFailure']=fatal
        record['sourceUnchanged']=hashlib.sha256(board.read_bytes()).hexdigest()==record['inputSha256']
        results.append(record)
        print(f'{b["id"]}: '+('COMMAND FAILED' if fatal else 'DRC violations — inspect report' if record['drcViolationsReported'] else 'DRC no reported violations'),flush=True)
        (args.output/'native-kicad-review.json').write_text(json.dumps(report,indent=2))
    report['finishedUtc']=datetime.now(timezone.utc).isoformat()
    report['allCommandsCompleted']=all(not b['commandFailure'] for b in results)
    report['anyDrcViolations']=any(b.get('drcViolationsReported') for b in results)
    report['allSourcesUnchanged']=all(b['sourceUnchanged'] for b in results)
    (args.output/'native-kicad-review.json').write_text(json.dumps(report,indent=2))
    print('Native results saved. Inspect DRC, board outlines, NPTH slots, gold/mask registration and each CAM layer before releasing an order.')
    if not report['allCommandsCompleted'] or not report['allSourcesUnchanged']:
        sys.exit(1)
    if report['anyDrcViolations']:
        sys.exit(5)


if __name__=='__main__':
    main()
