"""Millet Match - Streamlit demo over the rebuilt replacement mapping."""
from pathlib import Path
import math
import sys

import streamlit as st
import pandas as pd
import altair as alt

sys.path.insert(0, str(Path(__file__).parent))
st.set_page_config(page_title="Millet Match - Project Demo", page_icon="\U0001F33E", layout="wide")


@st.cache_resource
def load_engine():
    import millet_engine
    return millet_engine


try:
    engine = load_engine()
except (Exception, SystemExit) as exc:
    st.error("Could not load the project data: %s" % exc)
    st.info("Keep the mapping workbook, the nutrition CSV and millet_engine.py in the same folder as app.py.")
    st.stop()

GREEN = "#397650"
GREY = "#9fb0a2"
SLICE = {"Carb": "#8fb98a", "Protein": "#c79a5b", "Fat": "#d98c6a", "Fibre": "#2f6b43"}

st.markdown("""<style>
.stApp {background: #f6f7f2;}
h1, h2, h3 {color: #183e32;}
[data-testid="stSidebar"] {background: #eaf0e6;}
[data-testid="stMetric"] {background: white; padding: 12px 14px; border: 1px solid #dce4d8; border-radius: 12px;}
.eyebrow {color: #65836b; font-size: .8rem; letter-spacing: .16em; font-weight: 700;}
.intro {color: #52665a; max-width: 820px; font-size: 1.1rem;}
.chip {font-size:.72rem; font-weight:700; letter-spacing:.06em; padding:3px 9px; border-radius:20px; margin-left:8px;}
.chip-high {background:#d8ecd6; color:#2f6b43;} .chip-med {background:#fbeec7; color:#8a6a1b;} .chip-low {background:#f6dcd4; color:#9c4426;}
.verdict {font-weight:700;}
.lead-name {font-size:1.35rem; font-weight:800; color:#183e32;}
.reasons {color:#314d3c; font-size:.96rem;}
.tradeoff {color:#8a5a3a; font-size:.9rem;}
</style>""", unsafe_allow_html=True)

dishes_all = sorted({p['original'] for p in engine.MAPPING if p['original']})
default_dishes = [d for d in dishes_all if any(k in d.lower() for k in ('samosa', 'vermicelli kheer', 'pulao'))][:3]

with st.sidebar:
    st.title("\U0001F33E Millet Match")
    st.caption('BTP PROJECT - INTERACTIVE DEMO')
    conditions = st.multiselect('Health conditions', list(engine.DISEASES),
                                default=['Type 2 Diabetes', 'Chronic Kidney Disease', 'Hypertension'], key='conditions')
    dishes = st.multiselect('Dishes you would normally eat', dishes_all,
                            default=default_dishes or dishes_all[:3], key='dishes')
    st.caption('Pick familiar dishes and the conditions to screen for. Click an alternative to see the comparison.')
    st.divider()
    st.caption('Research demonstration. Results describe encoded directional rules on an equal-mass (per-100 g) basis, '
               'not clinical suitability or a prescribed diet.')

st.markdown('<div class="eyebrow">FROM EVERYDAY DISHES TO MILLET ALTERNATIVES</div>', unsafe_allow_html=True)
st.title('Find a millet match for your plate.')
st.markdown('<div class="intro">Choose dishes you already eat and the health conditions you want to account for. '
            'For each dish the tool ranks the millet versions; click one to open its nutrient comparison.</div>',
            unsafe_allow_html=True)
st.write('')
a, b = st.columns(2)
a.metric('Dishes selected', len(dishes))
b.metric('Conditions selected', len(conditions))


def finite(v):
    return v is not None and math.isfinite(float(v))


CONF_CLS = {'High': 'chip-high', 'Medium': 'chip-med', 'Low': 'chip-low'}


def conf_chip(conf):
    return '<span class="chip %s">%s MATCH</span>' % (CONF_CLS.get(conf, 'chip-med'), str(conf).upper())


def reasons_for(grain, millet, conditions):
    improvements, drawbacks = [], []
    if grain:
        for n in engine.NUTKEYS:
            if not finite(grain.get(n)) or not finite(millet.get(n)):
                continue
            change = millet[n] - grain[n]
            if not change:
                continue
            desc = ('More ' if change > 0 else 'Less ') + engine.NUTLABEL[n].lower()
            wanted = {engine.DISEASES[d][n] for d in conditions if n in engine.DISEASES[d]}
            if wanted and all(change * x > 0 for x in wanted):
                improvements.append(desc)
            elif wanted:
                drawbacks.append(desc)
    return improvements, drawbacks


def pie(values, title):
    labels = ['Carb', 'Protein', 'Fat', 'Fibre']
    values = [float(v) if (v is not None and math.isfinite(float(v))) else 0.0 for v in values]
    total = sum(values) or 1
    df = pd.DataFrame({'Nutrient': labels, 'grams': values,
                       'pct': [round(100 * v / total, 1) for v in values]})
    chart = (alt.Chart(df)
             .mark_arc(innerRadius=55, stroke='white', strokeWidth=1)
             .encode(theta=alt.Theta('grams:Q', stack=True),
                     color=alt.Color('Nutrient:N',
                                     scale=alt.Scale(domain=labels, range=[SLICE[x] for x in labels]),
                                     legend=alt.Legend(orient='bottom', title=None)),
                     order=alt.Order('Nutrient:N'),
                     tooltip=['Nutrient', alt.Tooltip('grams:Q', title='g/100g'),
                              alt.Tooltip('pct:Q', title='%')])
             .properties(height=280, title=title))
    return chart


def detail(pair, conditions, key):
    grain = engine.grain_nutrition(pair['replaced']) if pair['replaced'] else None
    millet = engine.millet_nutrition(pair['millet_recipe'], pair['millet_type'])
    improvements, drawbacks = reasons_for(grain, millet, conditions)

    if improvements:
        st.markdown('<span class="reasons"><b>Why consider it:</b> ' + ', '.join(improvements) + '.</span>',
                    unsafe_allow_html=True)
    if drawbacks:
        st.markdown('<span class="tradeoff"><b>Trade-off:</b> ' + ', '.join(drawbacks) + '.</span>',
                    unsafe_allow_html=True)
    if grain is None:
        st.caption('No comparable grain was mapped for this dish, so no nutrient comparison is available.')
        return

    macro = ['carb', 'protein', 'fat', 'fibre']
    c1, c2 = st.columns(2)
    c1.altair_chart(pie([millet[n] for n in macro], pair['millet_recipe']), use_container_width=True)
    c2.altair_chart(pie([grain[n] for n in macro], 'Original: ' + str(grain.get('matched_as', pair['replaced']))),
                    use_container_width=True)

    st.caption('Per 100 g, millet vs the ingredient it replaces:')
    cols = st.columns(5)
    units = {'kcal': 'kcal', 'carb': 'g', 'protein': 'g', 'fat': 'g', 'fibre': 'g'}
    for col, n in zip(cols, engine.NUTKEYS):
        if finite(millet.get(n)) and finite(grain.get(n)):
            d = round(millet[n] - grain[n], 1)
            # improvement direction depends on the selected conditions
            wanted = {engine.DISEASES[dd][n] for dd in conditions if n in engine.DISEASES[dd]}
            good = bool(wanted) and all(d * x > 0 for x in wanted)
            bad = bool(wanted) and all(d * x < 0 for x in wanted)
            # st.metric colours by sign; force green when good and red when bad, regardless of sign
            if good:
                dcolor = 'normal' if d > 0 else 'inverse'
            elif bad:
                dcolor = 'inverse' if d > 0 else 'normal'
            else:
                dcolor = 'off'
            col.metric('%s (%s)' % (engine.NUTLABEL[n], units[n]), round(millet[n], 1),
                       delta='%+.1f' % d, delta_color=dcolor)


def verdict_label(row, conditions):
    grain_ok = any(engine.verdict_for(row['pair'], d) != 'n/a' for d in conditions)
    if not grain_ok:
        return 'Incomplete assessment', 'off'
    if row['hurts']:
        return 'Best available trade-off', 'orange'
    if row['helps']:
        return 'Helps your conditions', 'green'
    return 'No clear gain', 'grey'


if not dishes or not conditions:
    st.info('Select at least one dish and one condition in the sidebar to see alternatives.')
else:
    _, conflicts = engine.combine_requirements(conditions)
    if conflicts:
        st.warning('Your selected conditions disagree on ' +
                   ', '.join(engine.NUTLABEL[n].lower() for n in conflicts) +
                   '. No single option can satisfy all of them, so the best choice may be a trade-off.')
    for di, dish in enumerate(dishes):
        ranked = engine.rank_alternatives([p for p in engine.MAPPING if p['original'] == dish], conditions)
        with st.container(border=True):
            st.subheader(dish)
            if not ranked:
                st.info('No millet alternative is mapped to this dish.')
                continue
            for ri, row in enumerate(ranked):
                pair = row['pair']
                vlabel, _ = verdict_label(row, conditions)
                lead = (ri == 0)
                head = ('⭐ ' if lead else '') + pair['millet_recipe'] + '   -   ' + vlabel
                with st.expander(head, expanded=lead):
                    st.markdown(('<span class="lead-name">%s</span>' % pair['millet_recipe']) +
                                conf_chip(pair.get('confidence')) +
                                '  &nbsp; <span class="verdict">%s</span>' % vlabel, unsafe_allow_html=True)
                    detail(pair, conditions, key='d%d_%d' % (di, ri))
