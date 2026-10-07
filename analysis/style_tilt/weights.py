# 백데이터 기반 버킷 내부 목표비중 산정
#  1) 고정 비중 w (5%p 그리드) — 전체기간 Sharpe 최대 + 전/후반 각각 최적의 평균(과최적화 완화)
#  2) 국면 틸트 — 국면별 최적 w를 그리드 탐색하되 고정 대비 ±15%p 이내, 전/후반 모두 고정보다 Sharpe 개선될 때만 채택
from tilt_bt import *
G = np.arange(0, 1.0001, 0.05)
def sharpe(r): return r.mean() / r.std() * np.sqrt(12)
def frame(a, b):
    d = pd.DataFrame({'a': a, 'b': b, 'reg': regime}).dropna(); return d[d.index <= END]
def best_static(d):
    return max(G, key=lambda w: sharpe(w * d.a + (1 - w) * d.b))
def run(name, a, b, cap=0.15):
    d = frame(a, b); mid = d.index[len(d) // 2]; h1, h2 = d[d.index < mid], d[d.index >= mid]
    w_all, w1, w2 = best_static(d), best_static(h1), best_static(h2)
    w0 = round(np.mean([w_all, w1, w2]) * 20) / 20           # 5%p 반올림
    best = (w0, w0, w0); base = [sharpe(w0 * x.a + (1 - w0) * x.b) for x in (h1, h2)]; score = 0
    for wb in G:
        for wr in G:
            if abs(wb - w0) > cap + 1e-9 or abs(wr - w0) > cap + 1e-9: continue
            res = []
            for x in (h1, h2):
                w = x.reg.map({'bull': wb, 'bear': wr, 'neutral': w0}); res.append(sharpe(w * x.a + (1 - w) * x.b))
            gain = [r - b_ for r, b_ in zip(res, base)]
            if min(gain) > 0 and sum(gain) > score: score, best = sum(gain), (wb, w0, wr)
    wb, wn, wr = best
    full = lambda w: sharpe(w * d.a + (1 - w) * d.b)
    tilt = d.reg.map({'bull': wb, 'bear': wr, 'neutral': wn})
    print(f'{name:28s} {d.index[0]}~ 고정최적 전체/전반/후반 {w_all:.0%}/{w1:.0%}/{w2:.0%} → 기준 {w0:.0%} | '
          f'틸트 강세/중립/약세 {wb:.0%}/{wn:.0%}/{wr:.0%} | Sharpe 고정 {full(w0):.3f} → 틸트 {sharpe(tilt*d.a+(1-tilt)*d.b):.3f}')
    # 채택 규칙: 전체기간 Sharpe 개선 0.01 미만이면 틸트 없이 기준 비중 고정 · 실무 분산 위해 5~95% 범위로 제한
    if sharpe(tilt*d.a+(1-tilt)*d.b) - full(w0) < 0.01: wb = wr = w0
    clip = lambda w: int(round(min(0.95, max(0.05, w)) * 100))
    out = (clip(wb), clip(wn), clip(wr)); print(f'{"":28s} → 앱 목표(A%) 강세/중립/약세 {out}'); return out
if __name__ == '__main__':
    run('KR 대형(KODEX200)/소형(코스닥)', y('069500.KS'), y('%5EKQ11'))
    run('KR 수출/내수 (섹터 5:5)', kr_exp, kr_dom)
    run('US 가치(IWD)/성장(IWF)', y('IWD'), y('IWF'))
    run('US 대형(IWB)/소형(IWM)', y('IWB'), y('IWM'))
