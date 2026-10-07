# 국면(강세/중립/약세)별 주식 스타일 스프레드 분석 — 국내·해외 주식 내부 비중 틸트 근거
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'regime_weights'))
from sig import *            # sig_series, overall, fred, monthly, retail_yoy, ism_s, yahoo(regime data dir)
from scipy import stats
HERE = os.path.dirname(os.path.abspath(__file__)); SD = os.path.join(HERE, 'data')

def y(t):
    j = json.load(open(os.path.join(SD, f'y_{t}.json')))['chart']['result'][0]
    q = j['indicators']; px = q['adjclose'][0]['adjclose'] if 'adjclose' in q else q['quote'][0]['close']
    s = pd.Series(px, index=pd.to_datetime(j['timestamp'], unit='s')).dropna()
    s.index = s.index.to_period('M'); s = s[~s.index.duplicated(keep='last')]
    return s.pct_change(fill_method=None)
def ff(fname, after=None):
    """Ken French CSV: (after 라인 이후) 첫 월간 표를 DataFrame(소수)으로."""
    lines = open(os.path.join(SD, fname)).read().splitlines()
    k = next(i for i, l in enumerate(lines) if after in l) if after else 0
    while not lines[k].startswith(','): k += 1
    hdr = [h.strip() for h in lines[k].split(',')][1:]; rows = []
    for l in lines[k+1:]:
        p = [x.strip() for x in l.split(',')]
        if not (p[0].isdigit() and len(p[0]) == 6): break
        rows.append(p)
    return pd.DataFrame([r[1:] for r in rows], columns=hdr, dtype=float,
                        index=pd.PeriodIndex([r[0][:4]+'-'+r[0][4:] for r in rows], freq='M')) / 100
ew = lambda *s: pd.concat(s, axis=1).mean(axis=1, skipna=True)

# ---- 국면 (앱과 동일 규칙, regime_weights/analysis.py와 동일 구성) ----
ppi = monthly(fred('PPIACO')); m3 = (ppi / ppi.shift(3) - 1) * 100
# 2026 ISM 실제값(앱 자동수집과 동일 출처)으로 DBnomics 공백 보완
ism_app = pd.Series({'2026-01': 59.0, '2026-02': 70.5, '2026-03': 78.3, '2026-04': 84.6, '2026-05': 82.1,
                     '2026-06': 73.0, '2026-07': 71.1, '2026-08': 71.1}); ism_app.index = pd.PeriodIndex(ism_app.index, freq='M')
ism_full = pd.concat([ism_s, ism_app]); ism_full = ism_full[~ism_full.index.duplicated(keep='last')].sort_index()
s_ism = pd.concat([sig_series(m3)[:'2020-12'], sig_series(ism_full)['2021-01':]]); s_ism = s_ism[~s_ism.index.duplicated()]
reg = overall(sig_series(retail_yoy), s_ism).dropna()
LAG = 2; regime = reg.copy(); regime.index = regime.index + LAG

# ---- 스프레드 (A − B, 현지통화 월수익률: 같은 시장 내 상대비중이라 환율 상쇄) ----
fac = ff('F-F_Research_Data_Factors.csv')
p6 = ff('6_Portfolios_2x3.csv', 'Average Value Weighted Returns -- Monthly')
kr_exp = ew(*[y(t) for t in ['091160.KS', '091180.KS', '117460.KS', '117680.KS', '102960.KS']])  # 반도체·자동차·에너지화학·철강·조선
kr_dom = ew(*[y(t) for t in ['091170.KS', '102970.KS', '117700.KS', '140700.KS', '139280.KS']])  # 은행·증권·건설·보험·필수소비재
SPREADS = {
    # 국내
    'KR 수출−내수 (섹터ETF 동일가중)':      kr_exp - kr_dom,
    'KR 대형−소형 (KODEX200−코스닥)':       y('069500.KS') - y('%5EKQ11'),
    'KR 가치−시장 (고배당−KODEX200)':       y('161510.KS') - y('069500.KS'),
    # 해외(미국)
    'US 가치−성장 (FF HML)':                fac['HML'],
    'US 대형−소형 (FF −SMB)':               -fac['SMB'],
    'US 가치−성장 (IWD−IWF)':               y('IWD') - y('IWF'),
    'US 대형−소형 (IWB−IWM)':               y('IWB') - y('IWM'),
    'US 경기민감−방어 (XLI·XLB·XLE − XLP·XLU·XLV)': ew(y('XLI'), y('XLB'), y('XLE')) - ew(y('XLP'), y('XLU'), y('XLV')),
    'US 기술−시장 (XLK−IWB)':               y('XLK') - y('IWB'),
}
END = pd.Period('2026-09', 'M')

def table(spreads, start=None, end=END):
    out = []
    for name, s in spreads.items():
        d = pd.DataFrame({'r': s, 'reg': regime}).dropna()
        d = d[(d.index <= end) & ((d.index >= pd.Period(start, 'M')) if start else True)]
        g = d.groupby('reg')['r']; ann = (g.mean() * 12 * 100)
        b, n_ = d.r[d.reg == 'bull'], d.r[d.reg == 'bear']
        t, p = stats.ttest_ind(b, n_, equal_var=False) if len(b) > 2 and len(n_) > 2 else (np.nan, np.nan)
        # 하위기간 일관성: 전반/후반 각각 (강세−약세) 부호
        mid = d.index[len(d)//2]; sg = []
        for part in (d[d.index < mid], d[d.index >= mid]):
            pb, pn = part.r[part.reg == 'bull'], part.r[part.reg == 'bear']
            sg.append('+' if pb.mean() > pn.mean() else '−' if len(pb) and len(pn) else '?')
        out.append({'spread': name, 'from': str(d.index[0]), 'bull': ann.get('bull'), 'neutral': ann.get('neutral'),
                    'bear': ann.get('bear'), 'n(b/n/b)': f"{len(b)}/{(d.reg=='neutral').sum()}/{len(n_)}",
                    'bull−bear': ann.get('bull', np.nan) - ann.get('bear', np.nan), 'p': p, 'halves': ''.join(sg)})
    return pd.DataFrame(out).set_index('spread').round(2)

if __name__ == '__main__':
    pd.set_option('display.width', 200); pd.set_option('display.max_colwidth', 48)
    print('국면 분포', regime[regime.index <= END].value_counts().to_dict(), ' 최근', regime[-6:].to_dict())
    print('\n[전체 가용기간] 연환산 스프레드 %, p=강세 vs 약세 Welch t-test, halves=전/후반 (강세−약세) 부호')
    print(table(SPREADS).to_string())
    print('\n[2007-01~ 공통기간]'); print(table(SPREADS, '2007-01').to_string())
