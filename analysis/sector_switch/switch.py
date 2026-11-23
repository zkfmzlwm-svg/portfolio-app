# 수출주/내수주(업종) · 성장주/가치주(재무 팩터) 분리 스위칭 검증
#  A. 수출 vs 내수: 미국 소매판매 YoY 3개월 연속 상승 → 수출, 3개월 연속 하락 → 내수, 그 밖엔 직전 포지션 유지
#  B. 성장 vs 가치: 미 국채 10년물 금리 상승 추세 → 가치, 하락 추세 → 성장
#  업종 분류는 TIGER 200 업종 ETF(2011~) 기준. 신호 시차: 소매판매 2개월(발표 지연), 금리 1개월.
import os, json
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, 'data')
END = pd.Period('2026-10', 'M')

def y(t):
    j = json.load(open(os.path.join(D, f'y_{t}.json')))['chart']['result'][0]
    q = j['indicators']; px = q['adjclose'][0]['adjclose'] if 'adjclose' in q else q['quote'][0]['close']
    s = pd.Series(px, index=pd.to_datetime(j['timestamp'], unit='s')).dropna()
    s.index = s.index.to_period('M'); s = s[~s.index.duplicated(keep='last')]
    return s.pct_change(fill_method=None)
def fred(id):
    d = pd.read_csv(os.path.join(D, f'{id}.csv')); d.columns = ['d', 'v']
    d = d[pd.to_numeric(d.v, errors='coerce').notna()]
    return pd.Series(d.v.astype(float).values, index=pd.PeriodIndex(pd.to_datetime(d.d), freq='M'))
def ff6():
    p = os.path.join(HERE, '..', 'style_tilt', 'data', '6_Portfolios_2x3.csv'); L = open(p).read().splitlines()
    k = next(i for i, l in enumerate(L) if 'Average Value Weighted Returns -- Monthly' in l)
    while not L[k].startswith(','): k += 1
    hdr = [h.strip() for h in L[k].split(',')][1:]; rows = []
    for l in L[k + 1:]:
        q = [x.strip() for x in l.split(',')]
        if not (q[0].isdigit() and len(q[0]) == 6): break
        rows.append(q)
    return pd.DataFrame([r[1:] for r in rows], columns=hdr, dtype=float,
                        index=pd.PeriodIndex([r[0][:4] + '-' + r[0][4:] for r in rows], freq='M')) / 100
ew = lambda *s: pd.concat(s, axis=1).mean(axis=1, skipna=True)

# ---- 업종 분류 (사용자 기준) ----
SECTORS = {   # 코드: (이름, 그룹)
    '139260.KS': ('IT(반도체·전자)', '수출'), '139290.KS': ('경기소비재(자동차)', '수출'),
    '139250.KS': ('에너지화학', '수출'), '139240.KS': ('철강소재', '수출'), '227550.KS': ('산업재(조선·기계)', '수출'),
    '139270.KS': ('금융(은행·보험)', '내수'), '139280.KS': ('필수소비재(경기방어)', '내수'),
    '143860.KS': ('헬스케어', '내수'), '315270.KS': ('커뮤니케이션(통신·플랫폼)', '내수'),
    '139220.KS': ('건설·기계', '제외'),
}
R = {k: y(k) for k in SECTORS}; k200 = y('069500.KS')
EXP = ew(*[R[k] for k, v in SECTORS.items() if v[1] == '수출'])
DOM = ew(*[R[k] for k, v in SECTORS.items() if v[1] == '내수'])

# ---- 신호 ----
lv = fred('MRTSSM44X72USS'); yoy = (lv / lv.shift(12) - 1) * 100
def state_rule(x, n=3):
    """n개월 연속 상승 → +1(수출), n개월 연속 하락 → −1(내수), 그 밖 직전 유지. 첫 신호 전 0"""
    up = pd.concat([(x.diff() > 0).shift(i) for i in range(n)], axis=1).all(axis=1)
    dn = pd.concat([(x.diff() < 0).shift(i) for i in range(n)], axis=1).all(axis=1)
    st, out = 0, []
    for u, d_ in zip(up, dn):
        st = 1 if u else -1 if d_ else st; out.append(st)
    return pd.Series(out, index=x.index)
ma3 = yoy.rolling(3).mean()
SIG_EXP = {'YoY 3개월 연속(제안)': state_rule(yoy, 3), 'MA3 2회 연속(앱 방식)': state_rule(ma3, 2)}
for k in SIG_EXP: SIG_EXP[k].index = SIG_EXP[k].index + 2          # 데이터월 t → t+2월 적용

g10 = fred('GS10')
SIG_RATE = {'10년물 3개월 변화': np.sign(g10 - g10.shift(3)), '10년물 vs 12개월 평균': np.sign(g10 - g10.rolling(12).mean()),
            '10년물 6개월 변화': np.sign(g10 - g10.shift(6))}
for k in SIG_RATE: SIG_RATE[k] = SIG_RATE[k].replace(0, np.nan).ffill(); SIG_RATE[k].index = SIG_RATE[k].index + 1  # +1 = 금리 상승 → 가치

def stats(r):
    r = r.dropna(); c = (1 + r).prod() ** (12 / len(r)) - 1; v = r.std() * np.sqrt(12)
    eq = (1 + r).cumprod(); return c * 100, c / v, (eq / eq.cummax() - 1).min() * 100
def test(nm, a, b, sig, start=None, extra=None):
    """sig=+1 → A, −1 → B, 0 → 50:50. 전면 전환(100:0)과 틸트(70:30) vs 50:50"""
    d = pd.DataFrame({'a': a, 'b': b, 's': sig}).dropna(); d = d[d.index <= END]
    if start: d = d[d.index >= pd.Period(start, 'M')]
    s = 0.5 * d.a + 0.5 * d.b; sp = d.a - d.b
    line = f'{nm:44s} {d.index[0]}~ ({len(d)}개월, A국면 {(d.s>0).mean()*100:.0f}%)'
    line += f'\n    스프레드 A−B 연환산: A국면 {sp[d.s>0].mean()*1200:+6.1f}% · B국면 {sp[d.s<0].mean()*1200:+6.1f}%'
    for lab, hi in (('전면전환', 1.0), ('70:30', 0.7)):
        w = d.s.map({1: hi, -1: 1 - hi, 0: 0.5}); r = w * d.a + (1 - w) * d.b; ex = r - s
        c, sh, m = stats(r); line += f'\n    {lab:6s} CAGR {c:6.2f}% Sharpe {sh:.2f} MDD {m:5.0f}% | 50:50 대비 {ex.mean()*1200:+.2f}%p (t {ex.mean()/ex.std()*np.sqrt(len(ex)):+.2f}) · 전환 {int((d.s.diff().abs()>0).sum())}회'
    c, sh, m = stats(s); line += f'\n    50:50  CAGR {c:6.2f}% Sharpe {sh:.2f} MDD {m:5.0f}%'
    if extra is not None:
        e = extra.reindex(d.index); c, sh, m = stats(e); line += f' | 시장 CAGR {c:6.2f}% Sharpe {sh:.2f} MDD {m:5.0f}%'
    print(line)

if __name__ == '__main__':
    print('=== 업종별 성과·국면 민감도 (TIGER 200 업종, KOSPI200 대비 초과수익 연환산 %) ===')
    se = SIG_EXP['YoY 3개월 연속(제안)']; sr = SIG_RATE['10년물 3개월 변화']
    print(f'{"업종":24s} {"그룹":4s} {"CAGR":>6s} | {"소매↑(수출국면)":>14s} {"소매↓(내수국면)":>14s} | {"금리↑":>7s} {"금리↓":>7s}')
    for k, (nm, g) in SECTORS.items():
        r = R[k]; d = pd.DataFrame({'r': r, 'm': k200, 'e': se, 'q': sr}).dropna(); d = d[d.index <= END]
        ex = d.r - d.m; c = stats(d.r)[0]
        print(f'{nm:24s} {g:4s} {c:6.1f} | {ex[d.e>0].mean()*1200:+14.1f} {ex[d.e<0].mean()*1200:+14.1f} | {ex[d.q>0].mean()*1200:+7.1f} {ex[d.q<0].mean()*1200:+7.1f}   ({d.index[0]}~)')
    print('\n=== A. 수출 vs 내수 (미국 소매판매 YoY) ===')
    for k, s in SIG_EXP.items():
        test(f'TIGER200 업종 수출:내수 · {k}', EXP, DOM, s, extra=k200)
    import sys; sys.path.insert(0, os.path.join(HERE, '..', 'style_tilt'))
    from style import kr_exp, kr_dom
    for k, s in SIG_EXP.items():
        test(f'[장기] KODEX 섹터 수출:내수 · {k}', kr_exp, kr_dom, s, extra=y('069500.KS'))
    print('\n=== B. 가치 vs 성장 (미 국채 10년물 추세) ===')
    p6 = ff6(); fv, fg = p6['BIG HiBM'], p6['BIG LoBM']
    for k, s in SIG_RATE.items():
        test(f'[장기] FF 대형 가치:성장 · {k}', fv, fg, s, start='1954-01')
        test(f'US IWD:IWF · {k}', y('IWD'), y('IWF'), s, extra=y('IVV'))
        test(f'KR KODEX MSCI가치:Fn성장 · {k}', y('275290.KS'), y('325010.KS'), s, extra=k200)
    print('\n현재 신호: 소매판매', {k: int(v.iloc[-1]) for k, v in SIG_EXP.items()}, '(+1 수출) · 금리', {k: int(v.iloc[-1]) for k, v in SIG_RATE.items()}, '(+1 가치)')
    print('소매판매 YoY 최근', yoy.iloc[-5:].round(1).to_dict(), ' 10년물 최근', g10.iloc[-6:].to_dict())
