"""The explicit ENIG plan, retained from revision 2. Layer numbers are one-based.

mask-only means no exposed copper artwork, copper rim or exposed mounting pad.
This is not a claim that the physical laminate contains no copper whatsoever.
The final fabrication files and the order's selected finish must agree.
"""

ENIG_LAYERS = {
    'spider-nest': (1, 3, 5, 7),
    'coral-vault': (1, 4),
    'fault-line': (1,),
    'kumiko-void': (1, 4, 7),
    'woven-maze': (1,),
}

RATIONALE = {
    'spider-nest': 'トップの巣模様と、指定した3枚の全面金層にENIGを残す。白3枚と赤い底板は単色。',
    'coral-vault': 'トップのサンゴ模様と第4層の全面金を残す。ほかの6枚はレジスト色で表現。',
    'fault-line': 'ENIGはトップの岩盤の亀裂模様だけ。下層は赤と黒の段差で深さを表現。',
    'kumiko-void': '立体感を作る黒3層の金の面を残す。赤・緑6層は単色。',
    'woven-maze': 'ENIGはトップの縁取りと迷路模様だけ。白4枚と下層の黒4枚は単色。',
}


def apply_finish(layer, design_id):
    """Remove ALL decorative copper from a non-ENIG PCB, not only visible lines."""
    selected = layer['index'] + 1 in ENIG_LAYERS[design_id]
    full_gold = layer.get('surface') == 'gold'
    if full_gold and not selected:
        raise ValueError(f'{design_id}: full-gold layer removed from ENIG plan')
    if selected:
        layer['finish'] = 'enig-fill' if full_gold else 'enig-art'
        layer['finishLabel'] = '全面ENIG' if full_gold else 'ENIG装飾'
    else:
        layer['finish'] = 'mask-only'
        layer['finishLabel'] = '露出銅箔なし'
        layer['surface'] = 'mask'
        layer['art'] = {'strokes': [], 'fills': []}
    return layer


def summary(design_id, total):
    enig = list(ENIG_LAYERS[design_id])
    plain = [i for i in range(1, total + 1) if i not in enig]
    return {
        'enigLayers': enig, 'maskOnlyLayers': plain,
        'enigCount': len(enig), 'maskOnlyCount': len(plain), 'totalLayers': total,
        'rationale': RATIONALE[design_id],
    }
