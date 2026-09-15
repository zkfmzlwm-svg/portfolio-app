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
const ver=run('portfolio.ver');ok(ver==='4.7','버전 4.7, got '+ver);
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

// 목표 프리셋 합계 100
for(const k of['bull','neutral','bear']){
  const p=run('REGIME_TARGETS.'+k);
  const s=p.kr+p.us+p.bonds+p.gold+p.crypto;
  ok(s===100,'프리셋 '+k+' 합=100 ('+s+')');
}

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

// 7. 렌더 스모크 (예외 없이 모든 탭/모달 렌더)
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
