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


// v6.4: 🎯 10억 목표 시뮬레이션 — Python(analysis/goal_sim/pick.py, V0=1억, 10년, 월 250만, 30/25/0/25/20, 4,000경로)과 대조
const W=run('FIXED_TARGETS');
ok(run('GOAL_L.length')===140&&run('GOAL_L.every(r=>r.length===5)'),'월수익률 140×5');
{const m=[0,1,2,3,4].map(j=>run(`GOAL_L.reduce((s,r)=>s+r[${j}],0)/GOAL_L.length`));ok(m.every(x=>Math.abs(x)<1e-3),'평균 제거됨 '+m.map(x=>x.toFixed(5)));}
const base=o=>Object.assign({W,monthly:250e4,months:120,v0:1e8,tax:0,krx:0,goal:10e8},o||{});
const r=run(`goalRun(${JSON.stringify(base())})`);
ok(Math.abs(r.p-60.2)<4,'P(≥10억) ≈ 60% (Python 60.2), got '+r.p.toFixed(1));
ok(Math.abs(r.med/1e8-11.43)<0.5,'중앙 ≈ 11.4억, got '+(r.med/1e8).toFixed(2));
ok(Math.abs(r.p10/1e8-5.98)<0.4,'하위10% ≈ 6.0억, got '+(r.p10/1e8).toFixed(2));
const rs=run(`goalRun(${JSON.stringify(base({W:run('STABLE_TARGETS')}))})`);
ok(Math.abs(rs.p-49.3)<4&&rs.p<r.p,'안정형 P ≈ 49% (Python 49.3) < 10억 목표형, got '+rs.p.toFixed(1));
const r400=run(`goalRun(${JSON.stringify(base({monthly:400e4}))})`);
ok(Math.abs(r400.p-82)<4,'월 400만 P ≈ 82%, got '+r400.p.toFixed(1));
const r0=run(`goalRun(${JSON.stringify(base({mu:[7,8,3.5,5,0]}))})`);
ok(Math.abs(r0.p-43)<4,'코인 0% 가정 P ≈ 43%, got '+r0.p.toFixed(1));
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
ok(run("switchingScreen()").includes('10억 목표형 고정 비중 운영')&&run("switchingScreen()").includes('스위칭 신호 준수 시'),'스위칭 탭에 10억 확률·신호 준수 효과');
run("portfolio.targets=Object.assign({},STABLE_TARGETS)");
ok(run('goalCardHtml()').includes('10억 목표형 비중(')&&run("switchingScreen()").includes('10억 목표형 비중으로 바꾸고'),'안정형이면 10억 목표형 전환 버튼');
run('applyFixedTargets()');ok(run('portfolio.targets.crypto')===20&&run('portfolio.targets.bonds')===0,'10억 목표형 적용');
run('applyStableTargets()');ok(run('portfolio.targets.bonds')===10,'안정형 적용');
run("portfolio.goal={amt:5,end:'2031-10',tax:false,pension:0,rate:13.2}");
ok(run('goalCardHtml()').includes('🎯 5억 목표 · 2031-10까지')&&run('goalCardHtml()').includes('절세 미반영'),'목표 변경 반영');
ok(run('migratePortfolio(JSON.parse(JSON.stringify(portfolio))).goal.amt')===5,'백업·마이그레이션 후 목표 유지');
console.log(`\n${pass} passed, ${fail} failed`);
