# 2000~ 개별 대표종목으로 2×2 칸 검증 (최근 편향 점검). 주의: 현재 살아남은 대형주만 골라 생존편향 있음
from switch import *
C = {'수출×가치': ['005380.KS', '000270.KS', '005490.KS', '051910.KS', '010140.KS', '009540.KS'],
     '수출×성장': ['005930.KS', '000660.KS', '006400.KS'],
     '내수×가치': ['055550.KS', '015760.KS', '017670.KS', '033780.KS'],
     '내수×성장': ['000100.KS', '068270.KS', '035420.KS']}
cell = {k: ew(*[y(t) for t in v]) for k, v in C.items()}; ks = y('%5EKS11') + 0.015 / 12   # KOSPI 가격지수 + 배당 1.5%
se = SIG_EXP['YoY 3개월 연속(제안)']; sr = SIG_RATE['10년물 3개월 변화']
d = pd.DataFrame({**cell, 'e': se, 'q': sr, 'm': ks}).dropna(); d = d[(d.index >= pd.Period('2000-07', 'M')) & (d.index <= END)]
PER = (('2000~2010', '2000-07', '2010-12'), ('2011~2026', '2011-01', '2026-10'), ('전체', '2000-07', '2026-10'))
def sub(a, b): return d[(d.index >= pd.Period(a, 'M')) & (d.index <= pd.Period(b, 'M'))]
if __name__ == '__main__':
    print('[칸별 KOSPI 대비 초과수익 %/년 — 지금 국면(수출·가치) 구간 / 전체]')
    for k in C:
        out = []
        for nm, a, b in PER:
            x = sub(a, b); cur = (x.e > 0) & (x.q > 0); ex = x[k] - x.m
            out.append(f'{nm} 지금국면 {ex[cur].mean()*1200:+6.1f} ({cur.sum()}개월) / 전체 {ex.mean()*1200:+5.1f}')
        print(f'  {k:6s} ' + ' | '.join(out))
    print('\n[배분안 CAGR % (KOSPI+배당 대비)]')
    def plan(x, xe, xd, vb, vg):
        e = x.e.map({1: xe, -1: xd, 0: .5}); v = x.q.map({1: vb, -1: vg, 0: .5})
        return e*v*x['수출×가치'] + e*(1-v)*x['수출×성장'] + (1-e)*v*x['내수×가치'] + (1-e)*(1-v)*x['내수×성장']
    for nm, a, b in PER:
        x = sub(a, b); r = {'타세션 2×2(75/30·65/30)': plan(x, .75, .30, .65, .30), '가치/성장만(수출 50 고정)': plan(x, .5, .5, .65, .30),
                            '4칸 25% 고정': plan(x, .5, .5, .5, .5), 'KOSPI': x.m}
        print(f'  {nm:10s} ' + ' · '.join(f'{k} {stats(v)[0]:5.1f}' for k, v in r.items()))
