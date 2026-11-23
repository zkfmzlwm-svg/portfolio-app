#!/usr/bin/env bash
# 한국 장기(1990~) 월봉: 네이버 증권 차트 API(분할 반영 종가, 배당 제외) + FRED 소매판매 구계열(1947~2001)
set -e
cd "$(dirname "$0")"; mkdir -p data/naver; cd data
for c in KOSPI; do curl -sS -A "Mozilla/5.0" -o "naver/$c.json" "https://api.stock.naver.com/chart/domestic/index/$c/month?startDateTime=198001010000&endDateTime=209912310000"; done
for c in 005380 000270 005490 004020 001230 010140 010620 011780 009830 \
         005930 000660 066570 009150 006400 \
         015760 017670 030200 033780 004370 007310 000810 005830 001450 055550 024110 \
         000100 006280 000640 008930 004170 035420 036570 068270; do sleep 0.5
  curl -sS -A "Mozilla/5.0" -o "naver/$c.json" "https://api.stock.naver.com/chart/domestic/item/$c/month?startDateTime=198001010000&endDateTime=209912310000"; done
for id in RETAIL GS10 MRTSSM44X72USS; do curl -sS -o $id.csv "https://fred.stlouisfed.org/graph/fredgraph.csv?id=$id"; done
