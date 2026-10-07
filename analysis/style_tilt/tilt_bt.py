# 주식 버킷 내부 틸트 백테스트 + 국면 라벨 순환이동(circular shift) 검정
from style import *
rng = np.random.default_rng(0)
def shift_p(s, n=2000):
    """국면 시계열을 통째로 순환 이동시켜 (강세−약세) 차이의 귀무분포 → 자기상관 보존 p값"""
    d = pd.DataFrame({'r': s, 'reg': regime}).dropna(); d = d[d.index <= END]
    obs = d.r[d.reg == 'bull'].mean() - d.r[d.reg == 'bear'].mean(); regs = d.reg.values; null = []
    for _ in range(n):
        k = rng.integers(12, len(d) - 12); rr = np.roll(regs, k)
        null.append(d.r.values[rr == 'bull'].mean() - d.r.values[rr == 'bear'].mean())
    return (np.abs(null) >= abs(obs)).mean()
def bt(a, b, w_static, w_bull, w_bear, w_neu=None, start=None):
    """버킷 = w*A + (1−w)*B, 국면별 w (월 리밸런싱, 비용 제외). 반환: 고정 vs 틸트 CAGR/변동성/Sharpe(무위험 0)"""
    w_neu = w_static if w_neu is None else w_neu
    d = pd.DataFrame({'a': a, 'b': b, 'reg': regime}).dropna(); d = d[d.index <= END]
    if start: d = d[d.index >= pd.Period(start, 'M')]
    w = d.reg.map({'bull': w_bull, 'bear': w_bear, 'neutral': w_neu})
    res = {}
    for nm, ww in (('고정', w_static), ('틸트', w)):
        r = ww * d.a + (1 - ww) * d.b
        cagr = (1 + r).prod() ** (12 / len(r)) - 1; vol = r.std() * np.sqrt(12)
        res[nm] = (round(cagr * 100, 2), round(vol * 100, 1), round(cagr / vol, 3))
    ex = (d.reg.map({'bull': w_bull, 'bear': w_bear, 'neutral': w_neu}) - w_static) * (d.a - d.b)
    res['초과 t'] = round(ex.mean() / ex.std() * np.sqrt(len(ex)), 2)
    return res, f'{d.index[0]}~{d.index[-1]}'

if __name__ == '__main__':
    print('[순환이동 검정 p값 — 국면 지속성(자기상관) 반영]')
    for k, s in SPREADS.items(): print(f'  {k:45s} p={shift_p(s):.2f}')
    kr200, kq = y('069500.KS'), y('%5EKQ11')
    print('\n[KR 대형(KODEX200)/소형(코스닥) — 고정 70/30 대비]')
    for wb, wr in ((0.8, 0.6), (0.9, 0.5), (0.85, 0.7), (0.8, 0.7)):
        print(f'  강세 {wb:.0%} / 약세 {wr:.0%}:', *bt(kr200, kq, 0.7, wb, wr))
    print('\n[KR 수출/내수 — 고정 60/40 대비 (강세 수출↑, 약세 내수↑)]')
    for wb, wr in ((0.7, 0.5), (0.8, 0.4)): print(f'  강세 {wb:.0%} / 약세 {wr:.0%}:', *bt(kr_exp, kr_dom, 0.6, wb, wr))
    print('\n[US 가치(IWD)/성장(IWF) — 고정 40/60 대비 (약세 성장↑)]')
    for wb, wr in ((0.4, 0.3), (0.5, 0.3), (0.4, 0.2)): print(f'  강세 {wb:.0%} / 약세 {wr:.0%}:', *bt(y('IWD'), y('IWF'), 0.4, wb, wr))
    print('\n[US 대형(IWB)/소형(IWM) — 고정 85/15 대비 (약세 대형↑)]')
    for wb, wr in ((0.8, 0.9), (0.75, 0.95), (0.85, 0.95)): print(f'  강세 {wb:.0%} / 약세 {wr:.0%}:', *bt(y('IWB'), y('IWM'), 0.85, wb, wr))
    print('\n[US 경기민감/방어 — 고정 50/50 대비]')
    cyc, dfn = ew(y('XLI'), y('XLB'), y('XLE')), ew(y('XLP'), y('XLU'), y('XLV'))
    for wb, wr in ((0.6, 0.5), (0.6, 0.4)): print(f'  강세 {wb:.0%} / 약세 {wr:.0%}:', *bt(cyc, dfn, 0.5, wb, wr))
