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


// v6.4: 🎯 10억 목표 시뮬레이션 — Python(analysis/goal_sim/pick.py, V0=1억, 10년, 월 250만, 20/35/5/25/15, 반기 1회, 4,000경로)과 대조
const W=run('FIXED_TARGETS');
ok(run('GOAL_L.length')===140&&run('GOAL_L.every(r=>r.length===5)'),'월수익률 140×5');
{const m=[0,1,2,3,4].map(j=>run(`GOAL_L.reduce((s,r)=>s+r[${j}],0)/GOAL_L.length`));ok(m.every(x=>Math.abs(x)<1e-3),'평균 제거됨 '+m.map(x=>x.toFixed(5)));}
const base=o=>Object.assign({W,monthly:250e4,months:120,v0:1e8,tax:0,krx:0,goal:10e8},o||{});
const r=run(`goalRun(${JSON.stringify(base())})`);
ok(Math.abs(r.p-57.2)<4,'P(≥10억) ≈ 57% (Python 57.2), got '+r.p.toFixed(1));
ok(Math.abs(r.med/1e8-10.77)<0.6,'중앙 ≈ 10.8억, got '+(r.med/1e8).toFixed(2));
ok(Math.abs(r.p10/1e8-6.17)<0.4,'하위10% ≈ 6.2억, got '+(r.p10/1e8).toFixed(2));
const rs=run(`goalRun(${JSON.stringify(base({W:run('STABLE_TARGETS')}))})`),rg=run(`goalRun(${JSON.stringify(base({W:run('GOALMAX_TARGETS')}))})`);
ok(Math.abs(rs.p-56.4)<4,'안정형 P ≈ 56% (Python 56.4), got '+rs.p.toFixed(1));
ok(Math.abs(rg.p-64.0)<4&&rg.p>r.p,'10억 확률형 P ≈ 64% (Python 64.0) > 기본, got '+rg.p.toFixed(1));
const r400=run(`goalRun(${JSON.stringify(base({monthly:400e4}))})`);
ok(Math.abs(r400.p-82.6)<4,'월 400만 P ≈ 83%, got '+r400.p.toFixed(1));
const r0=run(`goalRun(${JSON.stringify(base({mu:[7,8,3.5,5,0]}))})`);
ok(Math.abs(r0.p-40.1)<4,'코인 0% 가정 P ≈ 40%, got '+r0.p.toFixed(1));
const rk=run(`goalRun(${JSON.stringify(base({krx:3}))})`),rt=run(`goalRun(${JSON.stringify(base({tax:118.8e4}))})`);
ok(rk.p>r.p&&rt.p>r.p&&rt.med>r.med,'스위칭·절세 레버는 확률↑');
// 0원 시작·적립 0 → 0
ok(run(`goalRun(${JSON.stringify(base({v0:0,monthly:0}))}).med`)===0,'자산·적립 0 → 0');
// 설정·카드
ok(run('goalCfg().amt')===10&&/^\d{4}-\d{2}$/.test(run('goalCfg().end')),'목표 기본값 10억 · YYYY-MM');
ok(Math.abs(run('goalMonthsLeft()')-120)<=1,'기본 남은 기간 10년, got '+run('goalMonthsLeft()'));
ok(Math.abs(run('goalTaxRefund({tax:true,pension:900,rate:13.2})')-1188000)<1&&run('goalTaxRefund({tax:false,pension:900,rate:13.2})')===0,'세액공제 118.8만 / 미반영 0');
ok(run('goalTaxRefund({tax:true,pension:1500,rate:16.5})')===1485000,'납입 한도 900만 적용');
const t0=Date.now(),gh=run('goalCardHtml()'),dt=Date.now()-t0;
ok(gh.includes("10억 이상 확률")&&gh.includes("확률 50%에 필요한 월 적립")&&gh.includes("스위칭 신호 준수")&&gh.includes("ISA"),'목표 카드 렌더');
ok(!gh.includes("NaN")&&!gh.includes("undefined"),'목표 카드 NaN 없음');
console.log('  목표 카드 계산 '+dt+'ms');
ok(run("rebalScreen()").includes("id=\"goalCard\"")&&run("rebalScreen()").includes("계산 중"),"리밸런싱 탭에 목표 카드(비동기)");
ok(run("goalCardCached()")===run("goalCardCached()")&&run("_goalHtml.h").includes("10억 이상 확률"),"목표 카드 캐시");
ok(run("switchingScreen()").includes('고정 목표 비중 운영 (기본)')&&run("switchingScreen()").includes('스위칭 신호 준수 시'),'스위칭 탭에 10억 확률·신호 준수 효과');
run("portfolio.targets=Object.assign({},STABLE_TARGETS)");
ok(run('goalCardHtml()').includes('기본 비중(')&&run("switchingScreen()").includes('기본 비중으로 바꾸고')&&run('goalCardHtml()').includes('10억 확률형 비중 30/20/5/25/20'),'안정형이면 기본 전환 버튼 + 10억 확률형 비교 행');
run('applyFixedTargets()');ok(run('portfolio.targets.us')===35&&run('portfolio.targets.crypto')===15,'기본 비중 적용');
run('applyGoalMaxTargets()');ok(run('portfolio.targets.kr')===30&&run('portfolio.targets.crypto')===20,'10억 확률형 적용');
run('applyStableTargets()');ok(run('portfolio.targets.bonds')===10,'안정형 적용');
run("portfolio.goal={amt:5,end:'2031-10',tax:false,pension:0,rate:13.2}");
ok(run('goalCardHtml()').includes('🎯 5억 목표 · 2031-10까지')&&run('goalCardHtml()').includes('절세 미반영'),'목표 변경 반영');
ok(run('migratePortfolio(JSON.parse(JSON.stringify(portfolio))).goal.amt')===5,'백업·마이그레이션 후 목표 유지');
// v6.7: 💰 투자계좌 입금 기록
run("portfolio.deposits=[];portfolio.goal={amt:10,end:'2036-10',tax:true,pension:900,rate:13.2};monthly=250");
ok(Array.isArray(run('migratePortfolio(JSON.parse(JSON.stringify(INIT))).deposits'))||run('Array.isArray(portfolio.deposits)'),'deposits 배열');
{const ym=run("localYmd(new Date())").slice(0,7),y=ym.slice(0,4),lastY=(+y-1)+'-12-15';
 run(`portfolio.deposits=[{id:'a',date:'${ym}-01',amt:1000000,memo:'월급'},{id:'b',date:'${ym}-02',amt:500000,memo:''},{id:'c',date:'${lastY}',amt:3000000,memo:''}]`);
 const st=run('depositStats()');
 ok(st.month===1500000&&st.total===4500000&&st.n===3,'이번 달 150만 · 누적 450만, got '+st.month+'/'+st.total);
 ok(st.year===1500000,'올해 누적은 작년 제외');
 const h=run('depositCardHtml()');
 ok(h.includes('이번 달 100만 더 넣기'),'월 250만 − 150만 = 100만 더 넣기');
 ok(h.includes('10억까지 부족')&&h.includes('수익 없이 입금만으로')&&!h.includes('NaN')&&!h.includes('undefined'),'목표액까지 부족·입금만 기준 월액');
 ok(h.includes('계산 중')||h.includes('확률 50% 기준'),'확률 50% 기준 행');
 run('goalCardCached()');
 const h2=run('depositCardHtml()');
 ok(/확률 50% 기준 앞으로 더 넣을 총액<\/span><span[^>]*>[\d.]+[억만]/.test(h2),'목표 카드 계산 후 50% 기준 총액 표시');
 run(`portfolio.deposits.push({id:'d',date:'${ym}-03',amt:1500000,memo:''})`);
 ok(run('depositCardHtml()').includes('이번 달 목표 입금 완료 (+50만 초과)'),'월 목표 초과 표시');
 ok(run("rebalScreen()").includes('id=\"depositCard\"')&&run("rebalScreen()").indexOf('depositCard')<run("rebalScreen()").indexOf('goalCard')&&run("rebalScreen()").indexOf('월 투자 금액')<run("rebalScreen()").indexOf('depositCard'),'월 투자 금액 아래·🎯 카드 위에 입금 카드');
 ok(run('migratePortfolio(JSON.parse(JSON.stringify(portfolio))).deposits.length')===4,'백업·마이그레이션 후 입금 기록 유지');
 run("portfolio.goal.amt=0.001");ok(run('depositCardHtml()').includes('✓ 달성'),'목표 달성 시 ✓');
}
console.log(`\n${pass} passed, ${fail} failed`);
