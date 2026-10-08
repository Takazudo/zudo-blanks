#!/usr/bin/env python3
"""Fresh, scoped native/CAM order candidates with portable verification receipts."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import PIL
from PIL import Image, ImageDraw
import shapely

from order_profiles import DEFAULT_PROFILE, VARIANTS, load_profile, order_manifest, finish
from build_lower_panels import build
import verify_native_cam as native
import verify_lower_panels as lower

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    native.write_json(path, value)


def relative(path, root):
    return str(Path(path).resolve().relative_to(root.resolve()))


def safe_path(root, rel):
    path = Path(rel)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError(f'Non-relative bundle reference: {rel}')
    target = root / path
    if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'Unsafe bundle path: {rel}')
    return target


def check_drc(path, board_name):
    report = json.loads(path.read_text())
    required = {'source', 'coordinate_units', 'included_severities', 'kicad_version',
                'violations', 'unconnected_items'}
    if not required.issubset(report):
        raise ValueError(f'Malformed DRC report: {path}')
    if (report['source'] != board_name or report['coordinate_units'] != 'mm'
            or not str(report['kicad_version']).startswith('10.0.')
            or not {'error','warning','exclusion'}.issubset(report['included_severities'])
            or report['violations'] or report['unconnected_items']):
        raise ValueError(f'DRC failed or wrong source/version/severities: {path}')
    unknown = {i['key'] for i in report.get('ignored_checks', [])} - set(native.EXPECTED_IGNORED_DRC_CHECKS)
    if unknown:
        raise ValueError(f'Unclassified ignored DRC checks: {unknown}')


def export_individual(board, cli, output):
    target = output / 'individual-cam' / board['id']
    (target / 'cam').mkdir(parents=True)
    contract = native.parse_rule_contract(board, json.loads(native.POLICY.read_text()))
    for name, argv in native.kicad_commands(cli, board, target, True):
        print(f'{name}: {board["id"]}', flush=True)
        lower.run_cli(argv[0], argv[1:], target / (name+'.log'))
    check_drc(target / 'drc.json', Path(board['nativePath']).name)
    checks, details = native.verify_cam_board(board, target)
    files = native.cam_file_records(target / 'cam', details['gerberPaths'], details['npthPath'])
    package = native.make_board_zip(board, output, target, details, files)
    thumb = output / 'previews' / (board['id']+'.png')
    native.render_cam_thumbnail(board, details, thumb)
    if not native.current_source_status(board):
        raise ValueError(f'Source changed during export: {board["id"]}')
    return {'id':board['id'], 'nativeBoard': 'sources/'+board['nativeBoard'],
            'nativeSha256':board['nativeSha256'], 'projectSha256':board['projectSha256'],
            'drc':relative(target/'drc.json', output), 'checks':checks, 'ruleContract':contract,
            'preview':relative(thumb, output),
            'zip':{'path':'packages/'+package['name'], 'sha256':package['sha256']}}


def panel_preview(record, result, group, native_root, cam_root, output):
    cam = cam_root / record['id'] / 'cam'
    gerbers = {}
    for entry in result['camFiles']:
        path = cam / entry['name']
        if path.suffix.lower() in ('.drl', '.gbrjob') or 'user' in path.name.lower():
            continue
        parsed = native.parse_gerber(path)
        layer = native._gerber_layer_from_file(path, parsed)
        if layer:
            gerbers[layer] = parsed
    drill = next(cam.glob('*NPTH.drl'))
    board = {'id':record['id'], 'boardBoundsMm':[0,0,record['widthMm'],record['heightMm']]}
    details = {'parsedGerbers':gerbers, 'parsedDrills':native.parse_excellon(drill),
               'finish':group['finish'], 'maskColor':group['color']}
    native.render_cam_thumbnail(board, details, output)
    image = Image.open(output)
    draw = ImageDraw.Draw(image)
    for x in record['scoreXMm']:
        draw.line((15+x*2.4,45,15+x*2.4,45+record['heightMm']*2.4), fill=(20,150,210),width=1)
    for y in record['scoreYMm']:
        draw.line((15,45+y*2.4,15+record['widthMm']*2.4,45+y*2.4), fill=(20,150,210),width=1)
    image.save(output)


def stack_previews(profile, boards, output):
    """Nominal side elevations complement actual CAM front views; not fit approval."""
    image = Image.new('RGB', (1000, 600), 'white')
    draw = ImageDraw.Draw(image)
    draw.text((20,10), 'Nominal stack sides: 1.6 mm PCB / 3 mm gaps. Actual fit and scored-edge finish pending.', fill='black')
    for n, (name, spec) in enumerate(profile['series'].items()):
        x,y = 20+(n%2)*500, 50+(n//2)*270
        draw.text((x,y), name, fill='black')
        for index, board_id in enumerate(spec['boardIds']):
            b=boards[board_id]
            top=index==0
            yy=y+25+index*23
            draw.rectangle((x+(0 if top else 35),yy,x+405-(0 if top else 35),yy+8),
                           fill=native.MASK_RGB[b['maskColor']],outline='black')
            draw.text((x+410,yy), f'L{index+1:02d}',fill='black')
    image.save(output / 'previews/nominal-stack-sides.png')


def write_order_table(order, path):
    rows = ['# '+order['variant']+' order candidate', '',
            'Choose ONE alternative. Purchase only the ZIPs listed in this table; individual reference exports in the bundle are not additional orders.', '',
            '| Package | Kind | Color / finish | mm | Designs | Quantity | Produced | Blank cells | Surplus | ZIP |',
            '| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |']
    for p in order['packages']:
        rows.append(f"| {p['id']} | {p['kind']} | {p['color']} / {p['finish']} | {p['widthMm']} × {p['heightMm']} | {p['distinctDesigns']} | {p['quantity']} | {p['producedPieces']} | {p['unusedCells']*p['quantity']} | {sum(p['surplusByBoardId'].values())} | [{p['id']}.zip](../../{p['zip']['path']}) |")
    rows += ['', f"Requested: {order['requestedCompleteStacks']} stacks / {order['usefulBoardCount']} useful pieces. Complete-set supply: {order['completeStackYield']}. Surplus: {order['surplusFinishedBoards']}. Blank cells exclude rails and routed cutouts.",
             '', 'All packages: FR-4, 1.6 mm, 2 copper layers, 1 oz; no silkscreen, solder paste or plated holes. Each member occurs once per sheet. Exact member IDs, per-ID surplus, source/config and verification references are in order.json.',
             '', 'Prices, engineering/design fees, routing/scoring, ENIG/area effects, shipping and tax: **unknown**. No dated quote. Factory CAM/scoring, sheet handling and physical fit are pending. Fewer sheets do not prove savings.']
    path.write_text('\n'.join(rows)+'\n')


def checksum_manifest(output):
    files=sorted(p for p in output.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
    (output/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {relative(p,output)}\n' for p in files))


def verify_bundle(output, expected_source=None, expected_run_id=None):
    output=output.resolve()
    sums={}
    for line in (output/'SHA256SUMS').read_text().splitlines():
        digest, rel=line.split('  ',1)
        path=safe_path(output,rel)
        if rel in sums or not path.is_file() or sha(path)!=digest:
            raise ValueError(f'Missing, duplicate or stale bundle file: {rel}')
        sums[rel]=digest
    actual={relative(p,output) for p in output.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}
    if set(sums)!=actual:
        raise ValueError('Checksum inventory differs from bundle files')
    receipt=json.loads((output/'receipt.json').read_text())
    if receipt.get('status')!='pass_local_native_cam' or receipt.get('manufacturingRelease') is not False:
        raise ValueError('Bundle does not carry successful local verification')
    if expected_source and (receipt['source_commit']!=expected_source or receipt['trackedInputsDirty']):
        raise ValueError('Source commit mismatch or dirty tracked inputs')
    if expected_run_id and receipt['run_id']!=str(expected_run_id):
        raise ValueError('Run identity mismatch')
    profile, boards=load_profile(output/'inputs/profile.json')
    expected_ids=set(boards)
    individual=json.loads((output/'individual-verification.json').read_text())
    if Counter(b['id'] for b in individual)!=Counter(expected_ids):
        raise ValueError('Individual evidence membership mismatch')
    for record in individual:
        pcb=safe_path(output,record['nativeBoard'])
        if sha(pcb)!=record['nativeSha256'] or sha(pcb.with_suffix('.kicad_pro'))!=record['projectSha256']:
            raise ValueError('Source/project evidence mismatch')
        check_drc(safe_path(output,record['drc']),pcb.name)
    orders=[]
    for variant in receipt['variants']:
        order=json.loads((output/'variants'/variant/'order.json').read_text())
        expected=order_manifest(profile,variant,boards)
        for key in expected:
            if key in ('status','packages'):
                continue
            if order[key]!=expected[key]:
                raise ValueError(f'{variant}: stale order accounting: {key}')
        if len(order['packages'])!=len(expected['packages']):
            raise ValueError('Order package count differs')
        for p, wanted in zip(order['packages'],expected['packages']):
            if any(p.get(k)!=v for k,v in wanted.items()):
                raise ValueError('Order package membership/settings differ')
            package=safe_path(output,p['zip']['path'])
            if sha(package)!=p['zip']['sha256']:
                raise ValueError('Order ZIP hash mismatch')
            with zipfile.ZipFile(package) as archive:
                names=archive.namelist()
                if archive.testzip() or len(set(names))!=len(names):
                    raise ValueError('Invalid package ZIP')
                for name in names:
                    if Path(name).name!=name:
                        raise ValueError('ZIP must contain flat relative file names')
                if not any(n.endswith('.drl') for n in names) or len([n for n in names if n.endswith(('.gbr','.gm1','.gtl','.gbl','.gts','.gbs'))])<5:
                    raise ValueError('Incomplete CAM ZIP')
        orders.append(order)
    return {'status':'pass', 'source_commit':receipt['source_commit'], 'run_id':receipt['run_id'],
            'variants':receipt['variants'], 'files':len(sums), 'orderLines':[o['packageCount'] for o in orders]}


def run(args):
    output=args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a fresh empty output directory')
    (output/'logs').mkdir(parents=True,exist_ok=True)
    receipt={'status':'running','startedUtc':native.utc_now(),'manufacturingRelease':False}
    write(output/'logs/progress.json',receipt)
    try:
        profile, selected=load_profile(args.profile)
        inventory,evidence=native.load_inventory(selected_ids=set(selected))
        variants=list(VARIANTS) if args.variant=='all' else [args.variant]
        version,help_text=native._cli_info(args.kicad_cli,True)
        if not version.startswith('10.0.'):
            raise ValueError('Pinned compatible KiCad 10.0.x required')
        write(output/'logs/installed-cli-help.json',help_text)
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        dirty=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip())
        receipt.update(source_commit=commit,head_sha=os.environ.get('ART_ORDER_HEAD_SHA',commit),
            base_sha=os.environ.get('ART_ORDER_BASE_SHA'),run_id=os.environ.get('GITHUB_RUN_ID','local'),
            run_attempt=os.environ.get('GITHUB_RUN_ATTEMPT','1'),trackedInputsDirty=dirty,
            variants=variants,profileSha256=sha(args.profile),tools={'python':sys.version.split()[0],
            'shapely':shapely.__version__,'pillow':PIL.__version__,'kicad':version,
            'kicadImage':os.environ.get('KICAD_IMAGE')},inputHashes={})
        (output/'inputs').mkdir()
        shutil.copyfile(args.profile,output/'inputs/profile.json')
        for path in [native.POLICY,native.MANIFEST,native.NATIVE_GENERATION,
                     *HERE.glob('*.py'),* (ROOT/'scripts/art-order').glob('*')]:
            if not path.is_file():continue
            dest=output/'inputs'/path.relative_to(ROOT)
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(path,dest)
            receipt['inputHashes'][relative(dest,output)]=sha(dest)
        for board in inventory:
            for suffix in ('.kicad_pcb','.kicad_pro'):
                source=(ROOT/board['nativeBoard']).with_suffix(suffix)
                target=output/'sources'/source.relative_to(ROOT)
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source,target)
            # DRC and CAM consume the bundled byte-identical source copies.
            board['nativePath']=str(output/'sources'/board['nativeBoard'])
            board['projectPath']=str(Path(board['nativePath']).with_suffix('.kicad_pro'))
        individual=[]
        for board in inventory:
            individual.append(export_individual(board,args.kicad_cli,output))
            receipt.update(completedIndividuals=len(individual))
            write(output/'logs/progress.json',receipt)
        write(output/'individual-verification.json',individual)
        by_id={b['id']:b for b in individual}
        for variant in variants:
            target=output/'variants'/variant
            target.mkdir(parents=True)
            order=order_manifest(profile,variant,selected)
            record=build(target/'native',profile=args.profile,variant=variant,evidence_path=target/'native-panels.json')
            results={}
            for panel in record['panels']:
                print(f'{variant}: {panel["id"]}',flush=True)
                result=lower.export_and_verify(panel,selected,args.kicad_cli,target/'cam',
                    native_root=target/'native',source_root=output/'sources')
                check_drc(target/'cam'/panel['id']/'drc.json',panel['id']+'.kicad_pcb')
                result['zip']['path']=relative(result['zip']['path'],output)
                result['drcOriginalPath']=relative(result['drcOriginalPath'],output)
                group=next(p for p in order['packages'] if p['id']==panel['id'])
                preview=target/(panel['id']+'.png')
                panel_preview(panel,result,group,target/'native',target/'cam',preview)
                result['preview']=relative(preview,output)
                results[panel['id']]=result
                write(target/'panel-verification.json',list(results.values()))
                receipt.update(currentVariant=variant,completedPanels=len(results))
                write(output/'logs/progress.json',receipt)
            for package in order['packages']:
                package['zip']=(results[package['id']] if package['kind']=='scored_lower_grid' else by_id[package['id']])['zip']
            order['status']='pass_local_native_cam; factory_quote_CAM_fit_pending'
            write(target/'order.json',order)
            write_order_table(order,target/'ORDER.md')
        stack_previews(profile,selected,output)
        receipt.update(status='pass_local_native_cam',finishedUtc=native.utc_now())
        write(output/'logs/progress.json',receipt)
        write(output/'receipt.json',receipt)
        (output/'README.md').write_text('# Four-series order candidates\n\nChoose one alternative in variants/*/ORDER.md. Never purchase all ZIPs.\n\n34 byte-identical native sources, fresh DRC/CAM and previews are included. Blue score overlays mark full-span V-scores, not routed cuts. Stack-side images are nominal geometry, not physical-fit evidence.\n\nQuoted prices are unknown. Factory CAM/scoring, perforated sheet handling, edge appearance and physical fit remain pending. Native verification does not establish factory approval or savings.\n\nVerify SHA256SUMS and receipt.json after download using the checked-in --verify-bundle command.\n')
        checksum_manifest(output)
        print(json.dumps(verify_bundle(output),indent=2))
    except Exception as exc:
        receipt.update(status='failed',error=str(exc),finishedUtc=native.utc_now())
        write(output/'logs/progress.json',receipt)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',type=Path,default=DEFAULT_PROFILE)
    parser.add_argument('--variant',choices=('all',*VARIANTS),default='all')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--kicad-cli')
    parser.add_argument('--verify-bundle',type=Path)
    parser.add_argument('--expected-source')
    parser.add_argument('--expected-run-id')
    args=parser.parse_args()
    if args.verify_bundle:
        print(json.dumps(verify_bundle(args.verify_bundle,args.expected_source,args.expected_run_id),indent=2))
    else:
        if not args.output or not args.kicad_cli:
            parser.error('--output and --kicad-cli are required for generation')
        run(args)


if __name__=='__main__':
    main()
