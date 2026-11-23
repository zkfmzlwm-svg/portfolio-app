# 소매판매·ISM·10년물 금리를 하나의 신호로 합칠 수 있는지 검증
#  합성 방식: (1) 셋 다 같은 방향일 때만 전환(그 외 유지) (2) 다수결 2/3 (3) 점수 비례(−3~+3 → 비중 연속 조정)
#  비교 기준: 따로 쓰기 — 수출/내수 = 소매판매+ISM 동시, 가치/성장 = 금리
from ism_check import *
import sys; sys.path.insert(0, os.path.join(HERE, '..', 'style_tilt'))
r3 = pd.concat({'r': s_ret, 'i': s_ism, 'q': sig_v}, axis=1).dropna()
def hold(cond_up, cond_dn):
    st, out = 0, []
    for u, d_ in zip(cond_up, cond_dn): st = 1 if u else -1 if d_ else st; out.append(st)
    return pd.Series(out, index=r3.index)
score = r3.sum(axis=1)                                     # −3 ~ +3
C_ALL = hold(score == 3, score == -3)
C_MAJ = np.sign(score).astype(int)                         # 셋 다 ±1이라 0 없음 → 다수결
SEP_E = both(s_ret, s_ism)
def kr(x, ew_, vw_):
    """ew_/vw_: 수출 비중·가치 비중 시계열(0~1)"""
    e, v = ew_.reindex(x.index).fillna(.5), vw_.reindex(x.index).fillna(.5)
    return e*v*x['수출×가치'] + e*(1-v)*x['수출×성장'] + (1-e)*v*x['내수×가치'] + (1-e)*(1-v)*x['내수×성장']
st2w = lambda s, hi, lo: s.map({1: hi, -1: lo, 0: .5})
CASES = {
    '따로 쓰기 (소매+ISM → 수출/내수, 금리 → 가치/성장)': (st2w(SEP_E, .75, .30), st2w(sig_v, .65, .30)),
    '합성① 셋 다 같은 방향 → 두 축 동시': (st2w(C_ALL, .75, .30), st2w(C_ALL, .65, .30)),
    '합성② 다수결(2/3) → 두 축 동시': (st2w(C_MAJ, .75, .30), st2w(C_MAJ, .65, .30)),
    '합성③ 점수 비례 (50±점수×8%p)': (.5 + score * .0833, .5 + score * .0833),
}
if __name__ == '__main__':
    x = d.copy(); base = kr(x, pd.Series(.5, index=x.index), pd.Series(.5, index=x.index))
    print(f'[국내 2×2] {x.index[0]}~{x.index[-1]} — 4칸 고정 대비 %p/년 (t), 10년대')
    for nm, (e, v) in CASES.items():
        r = kr(x, e, v); ex = r - base
        dec = ' '.join(f'{ex[(ex.index>=pd.Period(a,"M"))&(ex.index<=pd.Period(c,"M"))].mean()*1200:+.1f}' for _, a, c in PER[:4])
        sw = int((e.reindex(x.index).diff().abs() > 0).sum())
        print(f'  {nm:44s} {ex.mean()*1200:+.2f}%p (t {ex.mean()/ex.std()*np.sqrt(len(ex)):+.2f}) | {dec} | 비중 변경 {sw}회')
    # 해외: 가치/성장만 — FF 대형 가치:성장 1968~, IWD:IWF 2000~
    from style import p6, y as yy
    print('\n[해외 가치:성장] 50:50 고정 대비 %p/년 (t)')
    for lab, a, b in (('FF 대형 1968~', p6['BIG HiBM'], p6['BIG LoBM']), ('IWD:IWF 2000~', yy('IWD'), yy('IWF'))):
        for nm, sg in (('금리만 (현재)', st2w(sig_v, .65, .30)), ('합성① 셋 다', st2w(C_ALL, .65, .30)),
                       ('합성② 다수결', st2w(C_MAJ, .65, .30)), ('합성③ 점수 비례', .5 + score * .0833)):
            z = pd.DataFrame({'a': a, 'b': b, 'w': sg}).dropna(); z = z[z.index <= END]
            ex = z.w * z.a + (1 - z.w) * z.b - (.5 * z.a + .5 * z.b)
            print(f'  {lab:14s} {nm:12s} {ex.mean()*1200:+.2f}%p (t {ex.mean()/ex.std()*np.sqrt(len(ex)):+.2f})')
    print('\n현재: 소매', int(s_ret.iloc[-1]), 'ISM', int(s_ism.iloc[-1]), '금리', int(sig_v.iloc[-1]), '→ 점수', int(score.iloc[-1]))
