"""Engine for the rebuilt millet replacement mapping.
Reads the new mapping workbook (explicit replaced ingredient + confidence) and the
per-100g nutrition table, and scores millet alternatives against condition rules.
Public API mirrors the previous engine so the Streamlit app stays thin:
  MAPPING, DISEASES, NUTKEYS, NUTLABEL,
  grain_nutrition, millet_nutrition, combine_requirements,
  verdict_for, rank_alternatives
"""
import os, glob, re, difflib
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
NUTKEYS = ['kcal', 'carb', 'protein', 'fat', 'fibre']
NUTLABEL = {'kcal': 'Energy', 'carb': 'Carb', 'protein': 'Protein', 'fat': 'Fat', 'fibre': 'Fibre'}


def _find(patterns, label):
    for pat in patterns:
        hits = glob.glob(os.path.join(HERE, pat))
        if hits:
            return hits[0]
    raise FileNotFoundError("Missing the %s. Looked for %s in %s" % (label, patterns, HERE))

MAP_FILE = _find(['*Replacement_Mapping*REBUILD*.xlsx', '*Replacement*Mapping*.xlsx', '*Mapping*.xlsx'], 'mapping workbook')
NUT_FILE = _find(['*Nutrition*100*.csv', '*Nutrition*.csv', '*utrition*.csv'], 'nutrition CSV')


# ---------- nutrition table (per 100 g) ----------
def _num(v):
    s = str(v).strip().replace('–', '-')
    if s in ('', '-', 'nan') or 'source' in s.lower():
        return np.nan
    m = re.findall(r'\d+\.?\d*', s)
    return round(sum(map(float, m)) / len(m), 2) if m else np.nan

_nut = pd.read_csv(NUT_FILE)
for _c, _k in {'Energy (kcal/100g)': 'kcal', 'Carbohydrates (g/100g)': 'carb',
               'Protein (g/100g)': 'protein', 'Fat (g/100g)': 'fat',
               'Dietary Fibre (g/100g)': 'fibre'}.items():
    _nut[_k] = _nut[_c].map(_num)
_BYID = _nut.set_index('ID')
_NAMES = []
for _, _r in _nut.iterrows():
    for _nm in {str(_r['Standard Ingredient']).lower(), str(_r['Form / Variety']).lower()}:
        if _nm and _nm != 'nan':
            _NAMES.append((_nm, {k: (None if pd.isna(_r[k]) else float(_r[k])) for k in NUTKEYS},
                           str(_r['Standard Ingredient'])))


def grain_nutrition(name):
    """Per-100g nutrition for a replaced ingredient name, or None if unmatched."""
    if not isinstance(name, str) or not name.strip():
        return None
    nm = name.lower()
    best, score, label = None, 0, None
    for cand, vals, lab in _NAMES:
        sc = difflib.SequenceMatcher(None, nm, cand).ratio()
        if nm in cand or cand in nm:
            sc = max(sc, 0.9)
        if sc > score:
            score, best, label = sc, vals, lab
    return dict(best, matched_as=label) if score >= 0.55 else None


# ---------- millet nutrition (per 100 g), with type resolution ----------
_BASE = {'Sorghum': 'A005', 'Pearl Millet': 'A003', 'Finger Millet': 'A010',
         'Little Millet': 'A016', 'Kodo Millet': 'A017', 'Proso Millet': 'NEW-01',
         'Foxtail Millet': 'NEW-03', 'Barnyard Millet': 'NEW-04'}
_ALIAS = {'Ragi': 'Finger Millet', 'Bajra': 'Pearl Millet', 'Jowar': 'Sorghum'}
_SPECIAL = {'Rajgira': 'A001', 'Quinoa': 'A009', 'Kuttu': 'NEW-21'}
_GENERIC = {'Multi Millet', 'Mixed Millet', 'Millet', 'Unspecified', '', None}
_BLEND = ['Sorghum', 'Finger Millet', 'Pearl Millet', 'Foxtail Millet']


def _row(idx):
    r = _BYID.loc[idx]
    return {k: round(float(r[k]), 2) for k in NUTKEYS}


def millet_nutrition(recipe_name, millet_type):
    t = (millet_type or '').strip()
    t = _ALIAS.get(t, t)
    if t in _BASE:
        return dict(_row(_BASE[t]), src=t)
    if t in _SPECIAL:
        return dict(_row(_SPECIAL[t]), src=t)
    # generic / blend
    vals = {k: round(sum(_row(_BASE[c])[k] for c in _BLEND) / len(_BLEND), 2) for k in NUTKEYS}
    return dict(vals, src='Millet blend (' + ', '.join(_BLEND) + ')')


# ---------- disease rules ----------
DISEASES = {
    'Type 2 Diabetes':        {'fibre': 1, 'carb': -1, 'fat': -1},
    'High Cholesterol':       {'fibre': 1, 'fat': -1, 'kcal': -1},
    'Cardiovascular Disease': {'fibre': 1, 'fat': -1},
    'Hypertension':           {'fibre': 1, 'kcal': -1},
    'Chronic Kidney Disease': {'protein': -1},
    'MASLD / Fatty Liver':    {'kcal': -1, 'carb': -1, 'fat': -1, 'fibre': 1},
    'Obesity / Overweight':   {'kcal': -1, 'fibre': 1},
    'Gout':                   {'carb': -1, 'fat': -1, 'fibre': 1, 'protein': -1},
    'Osteoporosis':           {'protein': 1},
    'Dental Caries':          {},
}


def resolve_disease(text):
    t = text.strip().lower()
    for name in DISEASES:
        if t in name.lower() or name.lower().startswith(t):
            return name
    hits = difflib.get_close_matches(text, list(DISEASES), n=1, cutoff=0.4)
    return hits[0] if hits else None


# ---------- load the rebuilt mapping ----------
def _load_mapping():
    df = pd.read_excel(MAP_FILE, sheet_name='Replacement Mapping')
    pairs = []
    for _, r in df.iterrows():
        status = 'ALTERNATIVE' if str(r.get('confidence')) in ('High', 'Medium') else 'RECOMMENDATION'
        pairs.append(dict(
            original_id=str(r.get('original_recipe_id')),
            original=r.get('original_recipe'),
            original_family=r.get('original_family'),
            millet_recipe=r.get('millet_recipe'),
            millet_type=r.get('millet_type') or 'Unspecified',
            replaced=(r.get('replaced_ingredient') if isinstance(r.get('replaced_ingredient'), str) else None),
            confidence=r.get('confidence'),
            status=status))
    return pairs

MAPPING = _load_mapping()


# ---------- combine conditions / detect conflicts ----------
def combine_requirements(diseases):
    wants = {}
    for d in diseases:
        for nut, direction in DISEASES[d].items():
            wants.setdefault(nut, set()).add(direction)
    agreed, conflicts = {}, []
    for nut, dirs in wants.items():
        if len(dirs) == 1:
            agreed[nut] = next(iter(dirs))
        else:
            conflicts.append(nut)
    return agreed, conflicts


# ---------- per-condition verdict ----------
def verdict_for(pair, disease):
    rule = DISEASES[disease]
    if not rule:
        return 'n/a'
    gn = grain_nutrition(pair['replaced']) if pair['replaced'] else None
    if gn is None:
        return 'n/a'
    mn = millet_nutrition(pair['millet_recipe'], pair['millet_type'])
    score = 0
    for nut, direction in rule.items():
        if mn.get(nut) is None or gn.get(nut) is None:
            continue
        dv = mn[nut] - gn[nut]
        score += 1 if dv * direction > 0 else (-1 if dv * direction < 0 else 0)
    return 'help' if score > 0 else ('hurt' if score < 0 else 'neutral')


def _direction_score(pair, diseases):
    gn = grain_nutrition(pair['replaced']) if pair['replaced'] else None
    if gn is None:
        return 0
    mn = millet_nutrition(pair['millet_recipe'], pair['millet_type'])
    total = 0
    for d in diseases:
        for nut, direction in DISEASES[d].items():
            if mn.get(nut) is None or gn.get(nut) is None:
                continue
            dv = round(mn[nut] - gn[nut], 1)
            total += 1 if dv * direction > 0 else (-1 if dv * direction < 0 else 0)
    return total


# ---------- rank a dish's alternatives across the selected conditions ----------
def rank_alternatives(pairs, diseases):
    scored = []
    for p in pairs:
        verdicts = {d: verdict_for(p, d) for d in diseases}
        helps = sum(v == 'help' for v in verdicts.values())
        hurts = sum(v == 'hurt' for v in verdicts.values())
        scored.append(dict(pair=p, verdicts=verdicts, helps=helps, hurts=hurts,
                           satisfies_all=(hurts == 0), total=_direction_score(p, diseases)))
    scored.sort(key=lambda s: (s['hurts'], -s['helps'], -s['total'],
                               0 if s['pair']['status'] == 'ALTERNATIVE' else 1))
    seen, out = set(), []
    for s in scored:
        name = s['pair']['millet_recipe']
        if name not in seen:
            seen.add(name)
            out.append(s)
    return out
