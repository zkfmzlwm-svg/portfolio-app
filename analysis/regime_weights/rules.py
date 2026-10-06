"""고정 틸트 규칙 비교 (하위기간별) — 최종 프리셋(C) 선정 근거"""
from bt import *
base = np.array([25, 25, 20, 20, 10]) / 100
def mk(bull, bear):
    W = {'neutral': base, 'bull': base + np.array(bull) / 100, 'bear': base + np.array(bear) / 100}
    return lambda t, g: W[g]
rules = {
    'static 25/25/20/20/10': ([0] * 5, [0] * 5),
    'OLD presets': ([2, 5, -8, -7, 8], [-7, -8, 10, 7, -2]),
    'A': ([0, 0, -5, 5, 0], [-5, 0, 0, 5, 0]),
    'B': ([5, 5, -10, 0, 0], [-5, -5, 5, 5, 0]),
    'C (채택)': ([0, 8, -8, 0, 0], [-5, -5, 0, 10, 0]),
    'D': ([0] * 5, [-4, -4, 4, 4, 0]),
}
for per, Rx in [('2003-01~2009-12', R['2003-01':'2009-12']), ('2010-01~2026-09', R['2010-01':]), ('2014-10~2026-09', R['2014-10':])]:
    print('\n', per, len(Rx))
    print(pd.DataFrame({k: stats_(run(Rx, mk(*v))) for k, v in rules.items()}).T.to_string())
