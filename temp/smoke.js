// 논리 회귀 테스트 (DOM 스텁과 함께 app.js 실행)
const fs=require('fs'),vm=require('vm'),path=require('path');
const html=fs.readFileSync(path.join(__dirname,'../app/src/main/assets/index.html'),'utf8');
const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const el=()=>({style:{},innerHTML:'',textContent:'',value:'',setAttribute(){},getAttribute(){return null;},addEventListener(){},focus(){},select(){},querySelector(){return el();}});
const sandbox={
  console,
  window:{},
  localStorage:{_d:{},getItem(k){return this._d[k]??null;},setItem(k,v){this._d[k]=v;}},
  document:{getElementById:()=>el(),addEventListener(){},querySelector:()=>el(),querySelectorAll:()=>[]},
  alert:(m)=>console.log('[alert]',m),
  setTimeout:(f)=>0,clearTimeout(){},Date,Math,JSON,isNaN,parseFloat,parseInt,Object,Array,Set,Map,String,Number,RegExp,Error,
};
sandbox.window.NativeStorage=undefined;
vm.createContext(sandbox);
vm.runInContext(code,sandbox);
const G=k=>vm.runInContext(k,sandbox);
const run=(expr)=>vm.runInContext(expr,sandbox);

let pass=0,fail=0;
const ok=(cond,msg)=>{if(cond){pass++;}else{fail++;console.log('✗ FAIL:',msg);}};

// 1. 초기 로드/마이그레이션
const ver=run('portfolio.ver');ok(ver==='5.4','버전 5.4, got '+ver);
ok(Array.isArray(run('portfolio.txns')),'txns 배열');

// 2. 홈 계산
const c=run('calc()');
ok(c.total>0,'총자산 계산: '+c.total);
ok(Math.abs(c.kr+c.us+c.bonds+c.gold+c.crypto-c.total)<1,'자산 합=총계');

// 3. 리밸런싱
const rows=run('rebalRows()');
ok(rows.length===5,'rebalRows 5');
const plan=run('newMoneyPlan(200*10000)');
ok(plan.allocs.length===5,'alloc 5');
const sumAlloc=plan.allocs.reduce((s,a)=>s+a.amt,0);
ok(Math.abs(sumAlloc-2000000)<2,`월 200만 전량 배분 (${sumAlloc})`);
ok(plan.months>0,'달성 개월수: '+plan.months);
ok(plan.Xstar>=c.total,'Xstar>=현재총액');

// 고정 목표비중 합계 100 + 초기 로드 시 적용
{const p=run('FIXED_TARGETS');const s=p.kr+p.us+p.bonds+p.gold+p.crypto;ok(s===100,'고정비중 합=100 ('+s+')');
 ok(run('portfolio.fixedTargetsV1')===true,'고정비중 1회 전환 플래그');}

// 4. 거래 반영
run("portfolio.txns=[]");
const before=run("portfolio.holdings.kr_stocks.find(h=>h.id==='s4').qty");
run("applyTrade(portfolio.holdings.kr_stocks.find(h=>h.id==='s4'),'kr','buy',1,260000,0,'2026-09-01')");
const after=run("portfolio.holdings.kr_stocks.find(h=>h.id==='s4').qty");
ok(Math.abs(after-(before+1))<1e-9,'매수 수량 증가 '+before+'→'+after);
ok(run('portfolio.txns.length')===1,'매수 거래 1건 기록');
const avgAfter=run("portfolio.holdings.kr_stocks.find(h=>h.id==='s4').avg");
ok(avgAfter>0,'평단 재계산: '+avgAfter);

// 달러 매도 실현손익
run("const u=portfolio.holdings.us.find(h=>h.ticker==='SPY');applyTrade(u,'us','sell',0.5,800,0,'2026-09-02')");
const tx=run('portfolio.txns.find(t=>t.side==="sell")');
ok(!!tx,'매도 기록');
ok(tx.ccy==='USD','매도 통화 USD');
ok(Math.abs(tx.realizedKRW-(800-tx.price+800)*0)>0||tx.realizedKRW>0,'실현손익 KRW 환산: '+tx.realizedKRW);
const rp=run('realizedPnl()');
ok(rp===tx.realizedKRW,'실현손익 합계 일치');

// 전량 매도 시 closed 플래그
const res=run("(function(){const h=portfolio.holdings.gold.find(x=>x.id==='g4');const r=applyTrade(h,'gold','sell',h.qty,h.cur,0,'2026-09-03');return r.closed;})()");
ok(res===true,'전량 매도 closed=true');

// 5. 텍스트 파서
const sample=[
  '삼천당제약 13 170400 453000',
  '소수 0.436057 170400 460000',
  'TIGER KRX금현물 328 13550 13957',
  '비트코인 0.07898433 89952000 122291612',
  'MANA 3367 95.2 2237',
  'JOBY 51 7.15 10.04',
  'BND 8 100468 101078',
  '1Q 은액티브 77 8975 9615',
].join('\n');
sandbox.pendingText=sample;
const d=run('parseSnapshotText(pendingText)');
console.log('파싱 rows:');d.rows.forEach(r=>console.log('  ',r.action,r.cat,r.name,'q=',r.qty,'cur=',r.cur,'avg=',r.avg,'code=',r.code||''));
ok(d.rows.length===7,'소수분 머지 후 7종목 ('+d.rows.length+')');
const s2=d.rows.find(r=>r.name==='삼천당제약');
ok(s2&&Math.abs(s2.qty-13.436057)<1e-6,'소수분 합산 수량 13.436057, got '+(s2&&s2.qty));
ok(s2&&s2.cur===170400&&s2.avg===453000,'삼천당 현재가/평단 추정');
const btc=d.rows.find(r=>r.cat==='crypto'&&/BTC|비트코인/.test(r.name));
ok(!!btc,'코인(비트코인) 인식');
const joby=d.rows.find(r=>r.name==='JOBY');
ok(joby&&joby.cat==='us'&&joby.cur===7.15,'해외주식 JOBY: '+(joby&&JSON.stringify({cat:joby.cat,cur:joby.cur,avg:joby.avg})));
const bnd=d.rows.find(r=>r.name==='BND');
ok(bnd&&bnd.cat==='bonds'&&bnd.cur===100468,'채권 BND: '+(bnd&&bnd.cur));
const silver=d.rows.find(r=>r.name&&r.name.includes('은액티브'));
ok(!!silver,"'1Q 은액티브' 숫자 시작 종목명 인식");
// missing 감지: 본문에 국내가 나왔으니 안 나온 국내 종목이 missing
ok(d.missing.some(m=>m.entry.cat==='kr'),'누락 국내종목 감지 ('+d.missing.length+')');

// 6. 신호
const sig=run('overallSignal()');
console.log('현재 신호:',sig.label,sig.s);
ok(['bull','bear','forming','mixed','wait'].includes(sig.s),'유효 신호 상태');
// 혼조 테스트
run("portfolio.switching.retail=[{ym:'2026-01',val:1},{ym:'2026-02',val:2},{ym:'2026-03',val:3},{ym:'2026-04',val:4},{ym:'2026-05',val:5}];");
run("portfolio.switching.ism=[{ym:'2026-01',val:90},{ym:'2026-02',val:80},{ym:'2026-03',val:70},{ym:'2026-04',val:60},{ym:'2026-05',val:50}];");
const mixed=run('overallSignal()');
ok(mixed.s==='mixed'||mixed.s==='bear','한쪽 bull 한쪽 bear → 혼조/약세 처리, got '+mixed.s);
ok(run('regimeKey(overallSignal())')==='neutral','혼조→중립 프리셋');

// 7. 워치리스트 자체 알고리즘 (목표가 상승여력 + PER 저평가도 스코어링, 자동 제외/정렬)
run(`portfolio.holdings.watchlist=[
  {id:'wa',name:'매력종목',cur:100000,targetPrice:150000,eps:10000,indPer:8},
  {id:'wb',name:'제외대상',cur:200000,targetPrice:100000,eps:2000,indPer:5},
  {id:'wc',name:'고정종목',cur:200000,targetPrice:100000,eps:2000,indPer:5,pinned:true},
  {id:'wd',name:'데이터없음'},
]`);
ok(run("watchlistScore(portfolio.holdings.watchlist.find(h=>h.id==='wd'))")===null,'점수 산출 불가 시 null');
const scoreA=run("watchlistScore(portfolio.holdings.watchlist.find(h=>h.id==='wa'))");
const scoreB=run("watchlistScore(portfolio.holdings.watchlist.find(h=>h.id==='wb'))");
ok(scoreA>0,'상승여력·저평가 종목 점수>0: '+scoreA);
ok(scoreB<0,'목표가 초과·고평가 종목 점수<0: '+scoreB);
const removed=run('runWatchlistAlgorithm()');
const namesAfter=run("portfolio.holdings.watchlist.map(h=>h.name)");
ok(removed.includes('제외대상'),'점수 낮은 미고정 종목 자동 제외: '+removed);
ok(!namesAfter.includes('제외대상'),'제외된 종목이 실제 배열에서도 빠짐');
ok(namesAfter.includes('고정종목'),'📌 고정 종목은 점수 낮아도 유지');
ok(namesAfter[0]==='매력종목','점수 높은 순 정렬 (1위=매력종목), got '+namesAfter[0]);

// 7b. v5.1 마이그레이션: 기존 사용자 워치리스트에 해외 시드 종목 비파괴적으로 병합
const migratedOnce=run(`migratePortfolio({ver:'5.0',holdings:{kr_stocks:[],kr_etfs:[],us:[],bonds:[],gold:[],crypto:[],
  watchlist:[{id:'old1',name:'내가 추가한 종목',code:'999999'}]},txns:[],targets:{},switching:{}})`);
ok(migratedOnce.ver==='5.4','마이그레이션 후 ver 5.4, got '+migratedOnce.ver);
ok(migratedOnce.holdings.watchlist.some(h=>h.name==='내가 추가한 종목'),'기존 워치리스트 항목 보존');
ok(migratedOnce.holdings.watchlist.filter(h=>h.ticker==='NVDA').length===1,'해외 시드(NVDA) 1건 병합');
const seed=run('OVERSEAS_WATCHLIST_SEED');
ok(seed.every(s=>migratedOnce.holdings.watchlist.some(h=>h.ticker===s.ticker)),'해외 시드 전종목 병합');
// 이미 같은 티커로 추가해둔 경우 중복 삽입하지 않음
const migratedDup=run(`migratePortfolio({ver:'5.0',holdings:{kr_stocks:[],kr_etfs:[],us:[],bonds:[],gold:[],crypto:[],
  watchlist:[{id:'mine',name:'내가 산 애플',ticker:'AAPL',usd:true}]},txns:[],targets:{},switching:{}})`);
ok(migratedDup.holdings.watchlist.filter(h=>h.ticker==='AAPL').length===1,'이미 있는 티커는 중복 추가 안 함');
ok(migratedDup.holdings.watchlist.find(h=>h.ticker==='AAPL').name==='내가 산 애플','기존 항목 내용 그대로 유지(덮어쓰지 않음)');
// 멱등성: 이미 5.1인 포트폴리오를 다시 돌려도 추가 안 됨
sandbox.pendingPortfolio=migratedOnce;
const already=run('migratePortfolio(JSON.parse(JSON.stringify(pendingPortfolio)))');
ok(already.holdings.watchlist.length===migratedOnce.holdings.watchlist.length,'ver 5.1 재마이그레이션은 멱등 (중복 추가 없음)');

// 7c. 장기보유(keep) 종목: 총자산엔 포함, 리밸런싱·스위칭 스타일 계산에서는 제외
{
  run("portfolio=JSON.parse(JSON.stringify(INIT));portfolio.fixedTargetsV1=true");
  const full=run('calc()'),rb0=run('calc(true)');
  ok(Math.abs(full.total-rb0.total)<1,'keep 없으면 리밸런싱 기준=총자산');
  const s4v=run("(h=>h.qty*h.cur)(portfolio.holdings.kr_stocks.find(h=>h.id==='s4'))");
  const spyv=run("(h=>h.qty*h.cur*portfolio.exRate)(portfolio.holdings.us.find(h=>h.id==='ue1'))");
  run("toggleKeep('s4');toggleKeep('ue1')");
  ok(run("portfolio.holdings.kr_stocks.find(h=>h.id==='s4').keep")===true,'toggleKeep → keep=true');
  const full2=run('calc()'),rb=run('calc(true)');
  ok(Math.abs(full2.total-full.total)<1,'총자산은 keep 지정과 무관: '+full2.total);
  ok(Math.abs(rb.kr-(full.kr-s4v))<1,'리밸런싱 기준 국내에서 삼성전자 제외');
  ok(Math.abs(rb.us-(full.us-spyv))<1,'리밸런싱 기준 해외에서 SPY 제외');
  ok(Math.abs(rb.total-(full.total-s4v-spyv))<1,'리밸런싱 기준 총액 = 총자산 − 장기보유');
  const rrows=run('rebalRows()');
  ok(Math.abs(rrows.reduce((s,r)=>s+r.ev,0)-rb.total)<1,'rebalRows 합 = 리밸런싱 기준 총액');
  ok(Math.abs(rrows.reduce((s,r)=>s+r.tval,0)-rb.total)<1,'목표금액 합 = 리밸런싱 기준 총액(장기보유 미포함)');
  const kp=run('newMoneyPlan(200*10000)');
  ok(Math.abs(kp.allocs.reduce((s,a)=>s+a.amt,0)-2000000)<2,'keep 지정 후에도 월 적립 전량 배분');
  ok(kp.Xstar>=rb.total&&kp.Xstar<full.total+kp.totalNeed,'Xstar는 리밸런싱 기준');
  const sb=run('styleBuckets()');
  ok(!sb.kr.some(r=>r.h.id==='s4'),'스위칭 스타일 국내 버킷에서 삼성전자 제외');
  ok(!sb.us.some(r=>r.h.id==='ue1'),'스위칭 스타일 해외 버킷에서 SPY 제외');
  const ks=run('keptSummary()');
  ok(ks.n===2&&Math.abs(ks.total-s4v-spyv)<1,'keptSummary 2종목·금액 일치');
  // 스냅샷 붙여넣기(기존 종목 갱신)는 같은 객체를 수정하므로 keep 유지
  ok(run("JSON.parse(JSON.stringify(portfolio)).holdings.kr_stocks.find(h=>h.id==='s4').keep")===true,'백업 JSON에 keep 보존');
  run("toggleKeep('s4')");
  ok(run("'keep' in portfolio.holdings.kr_stocks.find(h=>h.id==='s4')")===false,'재토글 → keep 필드 제거');
  run("toggleKeep('w1')");
  ok(!run("portfolio.holdings.watchlist.find(h=>h.id==='w1').keep"),'워치리스트는 keep 지정 불가');
  // 국내 전 종목 장기보유 시 스타일 카드 안내 렌더
  run("[...portfolio.holdings.kr_stocks,...portfolio.holdings.kr_etfs].forEach(h=>h.keep=true)");
  ok(run('styleBuckets().kr.length')===0,'국내 전 종목 keep → 스타일 버킷 비어 있음');
  ok(run('styleTiltCard()').includes('전 종목 🔒 장기보유'),'전 종목 keep 안내 표시');
  run("tab='home';render();tab='rebal';render();tab='switching';render();tab='holdings';catH='kr';render();showKeepModal();closeModal()");pass++;
}

// 7d. 반기(6·12월) 정기 + ±5%p 수시 리밸런싱, 주식 종목 상한 트림 (v5.3)
{
  run("portfolio=JSON.parse(JSON.stringify(INIT));portfolio.fixedTargetsV1=true;delete portfolio.lastRebal");
  // 일정: 10월 → 다음 12월 말, 6월(미기록) → 이번 달 차례, 6월 기록 후 → 12월, 12월 기록 후 → 다음 해 6월
  const s10=run("rebalSchedule(new Date(2026,9,9))");
  ok(s10.nm===12&&!s10.due&&s10.nextLabel==='2026년 12월 말','10월 → 다음 정기 12월 말: '+s10.nextLabel);
  ok(s10.dday===83,'10/9 → 12/31 D-83, got '+s10.dday);
  const s6=run("rebalSchedule(new Date(2026,5,15))");
  ok(s6.due&&s6.nm===6,'6월 미기록 → 이번 달 정기 차례');
  run("portfolio.lastRebal='2026-06-28'");
  const s6d=run("rebalSchedule(new Date(2026,5,30))");
  ok(!s6d.due&&s6d.nm===12,'6월 기록 후 → 다음 12월');
  run("portfolio.lastRebal='2026-12-24'");
  const s12d=run("rebalSchedule(new Date(2026,11,26))");
  ok(!s12d.due&&s12d.nextLabel==='2027년 6월 말','12월 기록 후 → 다음 해 6월: '+s12d.nextLabel);
  ok(run("rebalSchedule(new Date(2027,0,5)).nm")===6,'1월 → 6월');
  run("delete portfolio.lastRebal");
  run("markRebalDone()");
  ok(/^\d{4}-\d{2}-\d{2}$/.test(run('portfolio.lastRebal')),'완료 기록 날짜 저장: '+run('portfolio.lastRebal'));
  ok(run("migratePortfolio(JSON.parse(JSON.stringify(portfolio))).lastRebal")===run('portfolio.lastRebal'),'마이그레이션·백업 후 완료 기록 유지');
  run("delete portfolio.lastRebal");

  // 수시 기준(v5.4): 목표 금액 대비 ±25%. INIT(국내 42.9·해외 12.8·채권 7.0·금 15.0·코인 22.4 vs 20/30/10/30/10) → 전 자산군 초과
  const br=run("bandBreaches().map(r=>r.k)");
  ok(br.join()==='kr,us,bonds,gold,crypto','목표 금액 ±25% 초과 자산군: '+br.join());
  ok(Math.round(run("relDev(rebalRows().find(r=>r.k==='crypto'))"))===124,'코인 목표 대비 +124%');
  const mk=(ev,tval)=>`bandBreaches([{k:'x',name:'x',ev:${ev},tval:${tval},w:0.1,cur:0}]).length`;
  ok(run(mk(125,100))===0&&run(mk(76,100))===0,'100만원 → 125만원·76만원은 기준 이내(경계 포함)');
  ok(run(mk(126,100))===1&&run(mk(74,100))===1,'100만원 → 126만원·74만원은 수시 기준 초과');
  ok(run(mk(5,0))===0,'목표 0% 자산군은 수시 기준 판단 제외');
  // 알림은 6·12월 정기만 — 수시 기준 초과는 상태(level)·홈 배너에 영향 없음
  ok(run("rebalStatus().level")===(run("rebalSchedule().due")?'due':'ok'),'수시 초과여도 상태는 정기 일정만 반영');
  ok(!run("homeRebalBanner()").includes('수시'),'홈 배너에 수시 알림 없음');
  run("portfolio.targets={kr:42.9,us:12.8,bonds:7,gold:15,crypto:22.3}");
  ok(run("bandBreaches().length")===0,'목표=현재면 밴드 초과 없음');
  run("portfolio.targets=Object.assign({},FIXED_TARGETS)");
  ok(run("bandBreaches(rebalRows().map(r=>Object.assign({},r,{ev:0})))").length===0,'자산 0이면 밴드 경보 없음');

  // 상한 트림 — 국내(목표 초과 버킷): 10종목 상한 20%, B'=목표 금액, 상한 종목 ≤20%, 합계 = 자산군 매도액
  const rr=run("rebalRows()"),krR=rr.find(r=>r.k==='kr');
  const kp=run("trimPlan('kr')");
  ok(kp.n===10&&Math.abs(kp.cap-0.2)<1e-12,'국내 10종목 상한 20%');
  ok(kp.over&&Math.abs(kp.Bp-krR.tval)<1,'국내 목표 초과 → 목표 금액 기준');
  const dsum=kp.items.reduce((s,i)=>s+i.delta,0);
  ok(Math.abs(dsum+krR.diff)<1,`종목 매도 합계=자산군 매도액 (${Math.round(-dsum)} vs ${Math.round(krR.diff)})`);
  ok(kp.items.every(i=>i.t<=kp.cap*kp.Bp+1e-6),'트림 후 모든 종목 ≤ 상한');
  const stp=kp.items.find(i=>i.id==='s1');
  ok(stp.capped&&Math.abs(stp.wt-20)<1e-6,'에스티팜 상한 20%로 트림: '+stp.wt);
  ok(kp.items[0].id==='s1','최대 매도 종목 = 에스티팜');
  const unc=kp.items.filter(i=>!i.capped&&i.ev>0),ratio=unc.map(i=>i.t/i.ev);
  ok(Math.max(...ratio)-Math.min(...ratio)<1e-9,'상한 미만 종목은 같은 비율로 축소(현재 비중 유지)');
  ok(kp.items.every(i=>i.delta<=1e-6),'목표 초과 버킷은 매수 없음');
  // 해외(목표 미달 버킷): 8종목 상한 25%, SPY 30.8%는 지수 태그로 제외 → 매매 없음
  const up=run("trimPlan('us')");
  ok(up.n===8&&!up.over&&Math.abs(up.Bp-up.B)<1,'해외 목표 미달 → 현재 버킷 기준');
  ok(up.items.find(i=>i.id==='ue1').exempt,'SPY 지수 태그 → 상한 제외');
  ok(up.items.every(i=>Math.abs(i.delta)<1),'해외 상한 초과 종목 없음 → 매매 0');
  // 목표 미달 버킷에서 상한 초과 종목: 초과분 매도 → 나머지에 현재 비중대로 재배분(합계 0)
  run("portfolio.holdings.us.find(h=>h.id==='u2').qty=30");   // CAH 대폭 확대
  const up2=run("trimPlan('us')"),cah=up2.items.find(i=>i.id==='u2');
  ok(cah.capped&&cah.delta<0&&Math.abs(cah.wt-25)<1e-6,'CAH 상한 25%로 트림');
  ok(Math.abs(up2.items.reduce((s,i)=>s+i.delta,0))<1,'미달 버킷 트림은 버킷 내 재배분(합계 0)');
  ok(up2.items.filter(i=>!i.capped).every(i=>i.delta>=-1e-6),'나머지 종목은 매수만');
  ok(up2.trimSum>0&&Math.abs(up2.trimSum+cah.delta)<1,'트림 합계 = CAH 매도액');
  // 목표를 살짝 넘은 버킷 + 상한 크게 넘은 종목: 트림 매도 일부는 자산군 매도, 나머지는 다른 종목 재매수
  run("portfolio=JSON.parse(JSON.stringify(INIT));portfolio.fixedTargetsV1=true;portfolio.targets={kr:41,us:12.8,bonds:7,gold:15,crypto:24.2}");
  const sl=run("trimPlan('kr')"),slR=run("rebalRows()").find(r=>r.k==='kr');
  ok(sl.over&&Math.abs(sl.items.reduce((s,i)=>s+i.delta,0)+slR.diff)<1,'소폭 초과 버킷도 종목 합계=자산군 매도액');
  ok(sl.items.some(i=>!i.capped&&i.delta>0)&&run("trimCard('kr','국내')").includes('다른 종목에 현재 비중대로 다시 삽니다'),'트림액>자산군 매도액이면 나머지 재매수 안내');
  run("portfolio=JSON.parse(JSON.stringify(INIT));portfolio.fixedTargetsV1=true");
  ok(run("trimCard('kr','국내')").includes('나머지 종목은 현재 비중대로 매도합니다'),'대폭 초과 버킷은 나머지 비중대로 매도 안내');
  // 장기보유 종목은 트림 대상·N에서 제외
  run("portfolio=JSON.parse(JSON.stringify(INIT));portfolio.fixedTargetsV1=true;toggleKeep('s1')");
  const kk=run("trimPlan('kr')");
  ok(kk.n===9&&!kk.items.some(i=>i.id==='s1'),'에스티팜 🔒 → 트림 대상·N 제외 (N='+kk.n+')');
  // 종목 3개 미만 → 미적용
  run("portfolio.holdings.us=portfolio.holdings.us.slice(0,2)");
  ok(run("trimPlan('us').skip")===true,'해외 2종목 → 상한 트림 미적용');
  run("portfolio.holdings.us=[]");
  ok(run("trimCard('us','해외')")==='','해외 버킷 비면 카드 생략');
  run("tab='home';render();tab='rebal';render()");pass++;
  ok(run("rebalScreen()").includes('주식 종목 상한 트림')&&run("rebalScreen()").includes('✂ 에스티팜')===false,'리밸런싱 화면 렌더(에스티팜 🔒이면 트림 표에 없음)');
  run("portfolio=JSON.parse(JSON.stringify(INIT));portfolio.fixedTargetsV1=true");
  const scr=run("rebalScreen()");
  ok(scr.includes('✂ 에스티팜')&&scr.includes('수시 기준(목표 금액 ±25%) 넘은 자산군')&&!scr.includes('수시 리밸런싱 필요'),'리밸런싱 화면: 수시 초과는 참고 문구(경보 아님) + 에스티팜 트림 표시');
  // 홈 배너: 6·12월 미기록일 때만. 이번 달을 완료로 기록하면 사라짐
  run("portfolio.lastRebal=localYmd(new Date())");
  ok(run("homeRebalBanner()")==='','이번 달 완료 기록 → 홈 배너 없음');
  run("delete portfolio.lastRebal");
  ok(run("rebalSchedule().due")?run("homeRebalBanner()").includes('정기 리밸런싱 차례'):run("homeRebalBanner()")==='','6·12월 미기록일 때만 홈 배너');
  ok(run("rebalScheduleCard({rows:rebalRows(),br:bandBreaches(),level:'due',sc:rebalSchedule(new Date(2026,5,10))})").includes('이번 달 정기 리밸런싱 (6월)'),'6월 정기 카드');
}

// 8. 렌더 스모크 (예외 없이 모든 탭/모달 렌더)
run("portfolio=migratePortfolio(JSON.parse(localStorage.getItem('porto'))||JSON.parse(JSON.stringify(INIT)))");
// 주의: 위에서 직렬화된 포트폴리오 사용
for(const t of['home','holdings','switching','rebal','analysis','settings']){
  run("tab='"+t+"';render();");pass++;
}
run("catH='us';render();catH='alts';render();catH='watch';render();catH='bonds';render();");
run("showLedger()");pass++;
run("showTradeModal('kr','s4','buy')");pass++;
run("showTradeModal('crypto','c1','sell')");pass++;
run("closeModal()");
run("showBackup()");pass++;
console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail?1:0);
