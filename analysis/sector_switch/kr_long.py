# 한국 최대 기간(1990-04~) 2×2 스위칭 검증
#  데이터: 네이버 증권 월봉(분할 반영 종가, 배당 제외 — KOSPI 가격지수와 같은 기준), FRED 소매판매(1947~ 구계열 + 1992~ 신계열)
#  종목: 각 칸의 '1990년대' 대표 대형주(오늘의 승자 위주 선택을 피함). 1997년 외환위기 때 상장폐지된 은행·대우 등은
#        데이터가 없어 빠짐 → 남은 생존편향(특히 1990년대 내수×가치·수출×가치가 실제보다 좋게 나올 수 있음)
#  분할·감자 미반영 월(한 달 ×2.5 이상 또는 ×0.4 이하)은 수익률에서 제외
import os, json
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, 'data')
START, END = pd.Period('1990-04', 'M'), pd.Period('2026-10', 'M')

def nv(code):
    d = json.load(open(os.path.join(D, 'naver', f'{code}.json')))
    s = pd.Series({pd.Period(x['localDate'][:6], 'M'): x['closePrice'] for x in d}).sort_index()
    r = s.pct_change(fill_method=None); r[(r > 1.5) | (r < -0.6)] = np.nan
    return r[r.index >= START]
def fred(id):
    d = pd.read_csv(os.path.join(D, f'{id}.csv')); d.columns = ['d', 'v']; d = d[pd.to_numeric(d.v, errors='coerce').notna()]
    return pd.Series(d.v.astype(float).values, index=pd.PeriodIndex(pd.to_datetime(d.d), freq='M'))
ew = lambda *s: pd.concat(s, axis=1).mean(axis=1, skipna=True)

CELLS = {
    '수출×가치': {'005380': '현대차', '000270': '기아', '005490': 'POSCO', '004020': '현대제철', '001230': '동국제강',
               '010140': '삼성중공업', '010620': '현대미포조선', '011780': '금호석유', '009830': '한화솔루션'},
    '수출×성장': {'005930': '삼성전자', '000660': 'SK하이닉스', '066570': 'LG전자', '009150': '삼성전기', '006400': '삼성SDI'},
    '내수×가치': {'015760': '한국전력', '017670': 'SK텔레콤', '030200': 'KT', '033780': 'KT&G', '004370': '농심', '007310': '오뚜기',
               '000810': '삼성화재', '005830': 'DB손보', '001450': '현대해상', '055550': '신한지주', '024110': '기업은행'},
    '내수×성장': {'000100': '유한양행', '006280': '녹십자', '000640': '동아쏘시오', '008930': '한미사이언스', '004170': '신세계',
               '035420': 'NAVER', '036570': '엔씨소프트', '068270': '셀트리온'},
}
cell = {k: ew(*[nv(c) for c in v]) for k, v in CELLS.items()}
kospi = nv('KOSPI')

# ---- 신호 ----
old, new = fred('RETAIL'), fred('MRTSSM44X72USS')
yoy = pd.concat([((old / old.shift(12) - 1) * 100)[:'1992-12'], ((new / new.shift(12) - 1) * 100)['1993-01':]])
def state_rule(x, n=3):
    up = pd.concat([(x.diff() > 0).shift(i) for i in range(n)], axis=1).all(axis=1)
    dn = pd.concat([(x.diff() < 0).shift(i) for i in range(n)], axis=1).all(axis=1)
    st, out = 0, []
    for u, d_ in zip(up, dn):
        st = 1 if u else -1 if d_ else st; out.append(st)
    return pd.Series(out, index=x.index)
sig_e = state_rule(yoy); sig_e.index = sig_e.index + 2                       # +1 수출, −1 내수 (2개월 시차)
g10 = fred('GS10'); sig_v = np.sign(g10 - g10.shift(3)).replace(0, np.nan).ffill(); sig_v.index = sig_v.index + 1  # +1 가치

d = pd.DataFrame({**cell, 'e': sig_e, 'v': sig_v, 'm': kospi}).dropna(subset=['e', 'v', 'm'])
d = d[(d.index >= START) & (d.index <= END)]
d[list(CELLS)] = d[list(CELLS)].apply(lambda c: c.fillna(d.m))   # 칸이 빈 달(종목 상장 전 등)은 시장 수익률로 채움
PER = (('1990년대', '1990-04', '1999-12'), ('2000년대', '2000-01', '2009-12'), ('2010년대', '2010-01', '2019-12'),
       ('2020년대', '2020-01', '2026-10'), ('전체', '1990-04', '2026-10'))
sub = lambda a, b: d[(d.index >= pd.Period(a, 'M')) & (d.index <= pd.Period(b, 'M'))]
def cagr(r): r = r.dropna(); return ((1 + r).prod() ** (12 / len(r)) - 1) * 100
def mix(x, xe, xd, vb, vg):
    e = x.e.map({1: xe, -1: xd, 0: .5}); v = x.v.map({1: vb, -1: vg, 0: .5})
    return e*v*x['수출×가치'] + e*(1-v)*x['수출×성장'] + (1-e)*v*x['내수×가치'] + (1-e)*(1-v)*x['내수×성장']
RULES = {'2×2 (수출75/30·가치65/30)': (.75, .30, .65, .30), '수출/내수만 (75/30)': (.75, .30, .5, .5),
         '가치/성장만 (65/30)': (.5, .5, .65, .30), '4칸 25% 고정': (.5, .5, .5, .5)}

if __name__ == '__main__':
    print(f'기간 {d.index[0]}~{d.index[-1]} ({len(d)}개월) · 수출국면 {(d.e>0).mean()*100:.0f}% · 금리상승 {(d.v>0).mean()*100:.0f}%')
    print('\n[1] 축별 스프레드 (연환산 %p) — 신호가 맞으면 왼쪽 > 오른쪽')
    for nm, a, b in PER:
        x = sub(a, b); ex_ = ew(x['수출×가치'], x['수출×성장']) - ew(x['내수×가치'], x['내수×성장'])
        va_ = ew(x['수출×가치'], x['내수×가치']) - ew(x['수출×성장'], x['내수×성장'])
        print(f'  {nm:6s} 수출−내수: 수출국면 {ex_[x.e>0].mean()*1200:+6.1f} / 내수국면 {ex_[x.e<0].mean()*1200:+6.1f}  |  '
              f'가치−성장: 금리↑ {va_[x.v>0].mean()*1200:+6.1f} / 금리↓ {va_[x.v<0].mean()*1200:+6.1f}')
    print('\n[2] 지금 국면(수출+가치)에서 칸별 KOSPI 대비 초과 (%/년, 개월수)')
    for k in CELLS:
        out = []
        for nm, a, b in PER:
            x = sub(a, b); cur = (x.e > 0) & (x.v > 0); out.append(f'{nm} {(x[k]-x.m)[cur].mean()*1200:+6.1f}({cur.sum()})')
        print(f'  {k:6s} ' + ' · '.join(out))
    print('\n[3] 규칙별 CAGR % (KOSPI 가격지수 대비)')
    for nm, a, b in PER:
        x = sub(a, b); print(f'  {nm:6s} ' + ' · '.join(f'{k} {cagr(mix(x, *p)):5.1f}' for k, p in RULES.items()) + f' · KOSPI {cagr(x.m):5.1f}')
    print('\n[4] 전체 기간 규칙 − 4칸 고정 (연 %p, t)')
    base = mix(d, .5, .5, .5, .5)
    for k, p in list(RULES.items())[:3]:
        ex = mix(d, *p) - base; print(f'  {k:26s} {ex.mean()*1200:+.2f}%p (t {ex.mean()/ex.std()*np.sqrt(len(ex)):+.2f}) · 10년대별 ' +
                                      ' '.join(f'{(mix(sub(a,b),*p)-mix(sub(a,b),.5,.5,.5,.5)).mean()*1200:+.1f}' for _, a, b in PER[:4]))
