"""Explicit order selection and bounded, deterministic sheet supply accounting."""
from collections import Counter
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_PROFILE = HERE / 'order-profiles/four-art-series.json'
VARIANTS = ('individual', 'grouped', 'split-red')
SERIES = {'coral-vault': 8, 'fault-line': 9, 'kumiko-void': 9, 'spider-nest': 8}


def finish(board):
    return 'ENIG' if board['finish'].startswith('enig') else 'lead-free HASL'


def load_profile(path=DEFAULT_PROFILE):
    profile = json.loads(Path(path).read_text())
    inventory = json.loads((HERE.parent / 'pcb/manifest.json').read_text())['boards']
    expected = {b['id']: b for b in inventory
                if b['category'] == 'selected' and b['designId'] in SERIES}
    if len(expected) != 34 or any('kumiko' in i and '-wide-' not in i for i in expected):
        raise ValueError('Frozen four-series inventory changed')
    if profile.get('schemaVersion') != 1 or profile.get('id') != 'four-art-series':
        raise ValueError('Unsupported order profile')
    if set(profile['series']) != set(SERIES) or profile['railMm'] != 5:
        raise ValueError('Four-series selection and fixed 5 mm rails are required')
    selected = []
    for name, spec in profile['series'].items():
        ids = spec['boardIds']
        wanted = {i for i, b in expected.items() if b['designId'] == name}
        if len(ids) != SERIES[name] or set(ids) != wanted:
            raise ValueError(f'{name}: exact source ID membership differs')
        if type(spec['stacks']) is not int or spec['stacks'] < 1:
            raise ValueError('Stack quantities must be positive integers')
        selected.extend(ids)
    if Counter(selected) != Counter(expected.keys()):
        raise ValueError('Missing or duplicate selected source IDs')
    quantities = profile['supplierQuantities']
    if (not quantities or any(type(q) is not int or q < 1 for q in quantities)
            or quantities != sorted(set(quantities))):
        raise ValueError('Supplier quantities must be increasing positive integers')
    if set(profile['variants']) != set(VARIANTS):
        raise ValueError('Expected individual, grouped and split-red alternatives')
    for variant in VARIANTS:
        groups = profile['variants'][variant]['groups']
        if variant == 'individual':
            if groups:
                raise ValueError('Individual alternative must not group boards')
            continue
        members = []
        group_ids = []
        for group in groups:
            ids = group['memberIds']
            if not ids or ids != sorted(set(ids)):
                raise ValueError('Group members must be unique sorted IDs')
            group_ids.append(group['id'])
            members.extend(ids)
            if any(i not in expected or expected[i]['layerNumber'] == 1 for i in ids):
                raise ValueError('Only selected lowers may be grouped')
            if any(expected[i]['maskColor'] != group['color'] or
                   finish(expected[i]) != group['finish'] for i in ids):
                raise ValueError('Incompatible color or finish group')
            c, r = group['columns'], group['rows']
            if any(type(n) is not int or n < 1 for n in (c, r)) or c*r < len(ids):
                raise ValueError('Invalid grid capacity')
            if len(ids) == 1 and (c, r) != (1, 1):
                raise ValueError('Singleton lowers must be standalone')
            rail = profile['railMm'] if len(ids) > 1 else 0
            if any(not 70 <= n <= 475 for n in (c*101.3+rail*2, r*94.3+rail*2)):
                raise ValueError('Panel dimensions exceed frozen bounds')
        lower_ids = {i for i, b in expected.items() if b['layerNumber'] > 1}
        if Counter(members) != Counter(lower_ids):
            raise ValueError('Missing or duplicate lower group membership')
        if len(group_ids) != len(set(group_ids)):
            raise ValueError('Duplicate group ID')
    return profile, expected


def groups_for(profile, variant, boards):
    if variant not in VARIANTS:
        raise ValueError(f'Unknown variant: {variant}')
    groups = []
    for spec in profile['variants'][variant]['groups']:
        rail = profile['railMm'] if len(spec['memberIds']) > 1 else 0
        demand = max(profile['series'][boards[i]['designId']]['stacks'] for i in spec['memberIds'])
        quantities = [q for q in profile['supplierQuantities'] if q >= demand]
        if not quantities:
            raise ValueError(f'No supplier quantity covers demand {demand}')
        groups.append({**spec, 'railMm': rail,
                       'widthMm': round(spec['columns']*101.3+2*rail, 6),
                       'heightMm': round(spec['rows']*94.3+2*rail, 6),
                       'unusedCells': spec['columns']*spec['rows']-len(spec['memberIds']),
                       'quantity': quantities[0]})
    return groups


def order_manifest(profile, variant, boards):
    demand = {i: profile['series'][b['designId']]['stacks'] for i, b in boards.items()}
    packages = []
    grouped = set()
    for group in groups_for(profile, variant, boards):
        ids = group['memberIds']
        grouped.update(ids)
        packages.append({**group, 'id': 'lower-panel-'+group['id'] if len(ids)>1 else ids[0],
                         'kind': 'scored_lower_grid' if len(ids)>1 else 'routed_lower_singleton'})
    for i, b in sorted(boards.items()):
        if i in grouped:
            continue
        quantities = [q for q in profile['supplierQuantities'] if q >= demand[i]]
        if not quantities:
            raise ValueError(f'No supplier quantity covers {i}')
        packages.append({'id': i, 'kind': 'routed_standalone_top' if b['layerNumber']==1 else 'routed_lower_singleton',
                         'memberIds': [i], 'quantity': quantities[0], 'unusedCells': 0,
                         'color': b['maskColor'], 'finish': finish(b),
                         'widthMm': 101.3, 'heightMm': 128.5 if b['layerNumber']==1 else 94.3})
    supply = Counter()
    for p in packages:
        p.update(material='FR-4', thicknessMm=1.6, copperLayers=2, copperOz=1,
                 silkscreen=False, distinctDesigns=len(p['memberIds']),
                 copiesPerSheet={i: 1 for i in p['memberIds']},
                 producedPieces=p['quantity']*len(p['memberIds']),
                 grossAreaCm2=round(p['widthMm']*p['heightMm']/100, 4),
                 surplusByBoardId={i:p['quantity']-demand[i] for i in p['memberIds']})
        supply.update({i:p['quantity'] for i in p['memberIds']})
    if Counter(i for p in packages for i in p['memberIds']) != Counter(boards.keys()):
        raise ValueError('Each selected board must have exactly one purchase source')
    designs = {}
    for name, spec in profile['series'].items():
        count=len(spec['boardIds'])
        designs[name]={'requestedStacks':spec['stacks'], 'completeStacks':min(supply[i] for i in spec['boardIds']),
                       'boardsPerStack':count, 'nominalDepthMm':round(count*1.6+(count-1)*3,1)}
    stacks=sum(d['requestedStacks'] for d in designs.values())
    return {'schemaVersion':1, 'profileId':profile['id'], 'variant':variant,
            'status':'planning_only; native_CAM_verification_required',
            'selectedBoardCount':len(boards), 'packageCount':len(packages),
            'orderedSheetsAndStandaloneUnits':sum(p['quantity'] for p in packages),
            'usefulBoardCount':sum(demand.values()), 'producedBoardCount':sum(supply.values()),
            'demandByBoardId':demand, 'supplyByBoardId':dict(supply),
            'surplusByBoardId':{i:supply[i]-demand[i] for i in demand},
            'surplusFinishedBoards':sum(supply.values())-sum(demand.values()),
            'wasteCells':sum(p['unusedCells']*p['quantity'] for p in packages),
            'requestedCompleteStacks':stacks, 'completeStackYield':sum(d['completeStacks'] for d in designs.values()),
            'designs':designs, 'hardwareForRequestedStacks':{'screws':stacks*4,'nuts':stacks*4,
             'spacers':sum((SERIES[s]-1)*v['stacks']*4 for s,v in profile['series'].items())},
            'packages':packages, 'quote':{k:None for k in ('quotedOn','currency','pcbPrice','engineeringFees',
                'designFees','routingScoring','enigEffects','panelAreaEffects','shipping','tax','total')},
            'pendingExternal':['dated quote and offered quantities','factory CAM/scoring and residual web approval',
                'perforated-sheet handling and scored-edge appearance','physical stack and fastener fit']}
