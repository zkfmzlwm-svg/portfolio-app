#!/usr/bin/env bash
# 스타일 분석 원자료 → ./data  (국면 신호 원자료는 ../regime_weights/fetch.sh)
set -e
cd "$(dirname "$0")"; mkdir -p data; cd data
for t in %5EKQ11 069500.KS 091160.KS 091170.KS 091180.KS 117460.KS 117680.KS 102970.KS 102960.KS 117700.KS 140700.KS 139280.KS 161510.KS \
         IWD IWF IWM IWB XLK XLI XLB XLE XLP XLV XLU; do sleep 1
  curl -sS -A "Mozilla/5.0" -o "y_$t.json" "https://query1.finance.yahoo.com/v8/finance/chart/$t?period1=0&period2=9999999999&interval=1mo&events=div"; done
for f in F-F_Research_Data_Factors 6_Portfolios_2x3; do
  curl -sS -o $f.zip "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/${f}_CSV.zip" && unzip -o -q $f.zip && rm $f.zip; done
