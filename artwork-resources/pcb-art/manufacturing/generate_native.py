#!/usr/bin/env python3
"""Regenerate the 43 selected home boards from indexed manufacturing candidates.

Existing native edits are protected by the approved handoff manifest on the
first run, and by this generator's output manifest on subsequent runs.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import shapely
from shapely.geometry import Polygon

from repair_mask_candidate import HERE, ROOT, board_id, digest, export

REPO=ROOT.parents[1]
OUTPUT=HERE/'native-generation.json'
TEMPLATE=REPO/'panels/art-strip-mine/pcb-01-black/strip-mine-01.kicad_pro'


def home_path(design, layer):
    family=REPO/'panels'/f'art-{design["id"]}'
    return family/(board_id(design,layer)+'.kicad_pcb')


def project_content(stem):
    data=copy.deepcopy(json.loads(TEMPLATE.read_text()))
    rules=data['board']['design_settings']['rules']
    rules['min_clearance']=.25
    rules['min_copper_edge_clearance']=.30
    rules['min_hole_clearance']=.30
    rules['solder_mask_to_copper_clearance']=0.0
    data['meta']['filename']=stem+'.kicad_pro'
    data['schematic']['top_level_sheets']=[]
    return json.dumps(data,indent=2)+'\n'


def run():
    geom_path=HERE/'manufacturing-geometry.json'
    mask_path=HERE/'mask-repair-candidate.json'
    copper_path=HERE/'copper-repair-candidate.json'
    ledger_path=HERE/'copper-repair-ledger.json'
    data=json.loads(geom_path.read_text())
    masks=json.loads(mask_path.read_text())
    coppers=json.loads(copper_path.read_text())
    ledger=json.loads(ledger_path.read_text())
    compact={**coppers,'boards':[{k:v for k,v in b.items() if k!='afterCopperWkbHex'}
                                  for b in coppers['boards']]}
    if compact!=ledger:
        raise ValueError('Local copper geometry differs from indexed ledger')
    if masks['sourceGeometrySha256']!=digest(geom_path.read_bytes()):
        raise ValueError('Native input mask provenance mismatch')
    if coppers['sourceGeometrySha256']!=digest(geom_path.read_bytes()):
        raise ValueError('Native input copper provenance mismatch')
    if coppers['maskCandidateSha256']!=digest(mask_path.read_bytes()):
        raise ValueError('Native input copper/mask provenance mismatch')
    by_mask={b['boardId']:b for b in masks['boards']}
    by_copper={b['boardId']:b for b in coppers['boards']}
    approved=json.loads((ROOT/'pcb/manifest.json').read_text())
    approved_hashes={b['nativeBoard']:b['nativeBoardSha256'] for b in approved['boards']}
    previous=json.loads(OUTPUT.read_text()) if OUTPUT.exists() else None
    previous_hashes={b['nativeBoard']:b['sha256'] for b in previous['boards']} if previous else {}
    previous_project_hashes={b['project']:b['projectSha256']
                             for b in previous['boards']} if previous else {}
    planned=[]
    for family in data['designs']:
        design=(next(d for d in family['variants'] if d.get('variantId')=='wide')
                if family['id']=='kumiko-void' else family)
        for layer in design['layers']:
            target=home_path(design,layer)
            relative=str(target.relative_to(REPO))
            if not target.exists():
                raise ValueError(f'Missing selected home board: {relative}')
            actual=digest(target.read_bytes())
            allowed={approved_hashes.get(relative),previous_hashes.get(relative)}
            if actual not in allowed:
                raise ValueError(f'Native board has untracked manual edits: {relative}')
            project=target.with_suffix('.kicad_pro')
            if project.exists():
                current=digest(project.read_bytes())
                if current!=previous_project_hashes.get(str(project.relative_to(REPO))):
                    raise ValueError(f'Native project has untracked manual edits: {project}')
            planned.append((design,layer,target,project))
    assert len(planned)==43
    records=[]
    emitted=[]
    for design,layer,target,project in planned:
        name=board_id(design,layer)
        drills=export.drill_specs(layer,data['spec'])
        decorative=export.split_functional_holes(layer,drills)
        outline=Polygon(layer['outer'])
        edge_rings=[outline.exterior]+[p.exterior for p in decorative]
        if layer['finish']=='mask-only':
            copper=Polygon();mask=Polygon()
        else:
            mask=shapely.from_wkb(bytes.fromhex(by_mask[name]['afterMaskWkbHex']))
            copper=shapely.from_wkb(bytes.fromhex(by_copper[name]['afterCopperWkbHex']))
        cu_parts,cu_fragments=export.native_parts(copper)
        mask_parts,mask_fragments=export.native_parts(mask)
        if cu_fragments['areaMm2']>.00001 or mask_fragments['areaMm2']>.00001:
            raise ValueError(f'{name}: native polygon partition dropped non-grid art')
        native=export.native_board(name,layer,data['spec'],edge_rings,drills,cu_parts,mask_parts)
        native=native.replace('No exposed copper; quote non-ENIG finish separately',
                              'Lead-free HASL')
        export.check_sexpr(native)
        project_text=project_content(name)
        emitted.append((target,native,project,project_text))
        records.append({
            'boardId':name,
            'nativeBoard':str(target.relative_to(REPO)),
            'sha256':digest(native.encode()),
            'project':str(project.relative_to(REPO)),
            'projectSha256':digest(project_text.encode()),
            'edgeLoopCount':len(edge_rings),
            'npthRoundCount':sum(d['shape']=='circle' for d in drills),
            'npthSlotCount':sum(d['shape']=='oval' for d in drills),
            'nativeCopperPolygons':len(cu_parts),
            'nativeMaskPolygons':len(mask_parts),
            'copperSourceWkbSha256':digest(copper.wkb),
            'maskSourceWkbSha256':digest(mask.wkb),
        })
        print(name,records[-1]['nativeCopperPolygons'],
              records[-1]['nativeMaskPolygons'],flush=True)
    report={
        'status':'candidate; native KiCad load/DRC/CAM is issue 16, full art proof pending',
        'manufacturingGeometrySha256':digest(geom_path.read_bytes()),
        'maskCandidateSha256':digest(mask_path.read_bytes()),
        'copperCandidateSha256':digest(copper_path.read_bytes()),
        'copperLedgerSha256':digest(ledger_path.read_bytes()),
        'generatorSha256':digest(Path(__file__).read_bytes()),
        'selectedBoardCount':len(records),
        'boards':records,
    }
    for target,native,project,project_text in emitted:
        target.write_text(native)
        project.write_text(project_text)
    OUTPUT.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    run()
