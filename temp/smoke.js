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
const ver=run('portfolio.ver');ok(ver==='5.1','버전 5.1, got '+ver);
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
ok(migratedOnce.ver==='5.1','마이그레이션 후 ver 5.1, got '+migratedOnce.ver);
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
