#!/usr/bin/env bash
# 리밸런싱 주기·종목 단위 분석 원자료 → ./data  (자산군·스타일 원자료는 ../regime_weights/fetch.sh, ../style_tilt/fetch.sh)
set -e
cd "$(dirname "$0")"; mkdir -p data; cd data
# 국내 개별주: 2010년 전후 KOSPI 시총 상위(현존) + 코스닥 중소형 + 앱 보유 종목
for t in 005930 000660 005380 005490 051910 055550 012330 105560 000270 066570 096770 015760 034220 017670 006400 033780 \
         000810 009150 010130 011170 030200 010950 086790 004020 035420 036570 000720 003550 010120 068270 237690; do sleep 0.7
  curl -sS -A "Mozilla/5.0" -o "y_$t.KS.json" "https://query1.finance.yahoo.com/v8/finance/chart/$t.KS?period1=0&period2=9999999999&interval=1mo&events=div"; done
for t in 000250 067630 028300 035900 041510 086520 039030 058470 036930 078600 060280 064760 095610 053800; do sleep 0.7
  curl -sS -A "Mozilla/5.0" -o "y_$t.KQ.json" "https://query1.finance.yahoo.com/v8/finance/chart/$t.KQ?period1=0&period2=9999999999&interval=1mo&events=div"; done
# 미국 개별주: 2000년 전후 S&P 대형주 + 앱 보유 종목
for t in XOM GE MSFT C WMT PFE JNJ BAC INTC AIG IBM PG MO CVX JPM KO CSCO VZ WFC PEP HD MRK ABT AMGN T ORCL MMM UNH \
         CAH MCK COR AAPL AMZN NVDA; do sleep 0.7
  curl -sS -A "Mozilla/5.0" -o "y_$t.json" "https://query1.finance.yahoo.com/v8/finance/chart/$t?period1=0&period2=9999999999&interval=1mo&events=div"; done
# 생존편향 없는 보조자료: Ken French 49 산업 · 모멘텀 팩터
for f in F-F_Momentum_Factor 49_Industry_Portfolios; do
  curl -sS --http1.1 -o $f.zip "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/${f}_CSV.zip" && unzip -o -q $f.zip && rm $f.zip; done
