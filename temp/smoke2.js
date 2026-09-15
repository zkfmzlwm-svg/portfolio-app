const fs=require('fs'),vm=require('vm'),path=require('path');
const html=fs.readFileSync(path.join(__dirname,'../app/src/main/assets/index.html'),'utf8');
const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const el=()=>({style:{},innerHTML:'',textContent:'',value:'',setAttribute(){},getAttribute(){return null;},addEventListener(){},focus(){},select(){},querySelector(){return el();}});
const sandbox={console,window:{},localStorage:{_d:{},getItem(k){return this._d[k]??null;},setItem(k,v){this._d[k]=v;}},
 document:{getElementById:()=>el(),addEventListener(){},querySelector:()=>el(),querySelectorAll:()=>[]},
 alert:()=>{},setTimeout:()=>0,clearTimeout(){},Date,Math,JSON,isNaN,parseFloat,parseInt,Object,Array,Set,Map,String,Number,RegExp,Error};
vm.createContext(sandbox);vm.runInContext(code,sandbox);
const run=e=>vm.runInExpression=vm.runInContext(e,sandbox);
let pass=0,fail=0;const ok=(c,m)=>{c?pass++:(fail++,console.log('✗',m));};
// 평가금액/손익/수익률 컬럼이 섞인 실제 증권앱 텍스트
const text=[
 '종목명 보유수량 현재가 평균단가 평가금액 손익 수익률',
 '삼성전자 9 257,500 295,790 2,317,500 -344,610 -12.94%',
 'LG전자 8.003564 200,000 186,237 1,601,112 110,423 7.39%',
 '에스티팜 70 110,600 100,236 7,742,000 725,480 10.34%',
 'BORA 1920.043087 28.4 490.3 54529 -886603 -94.21%'
].join('\n');
sandbox.t=text;
const d=run('parseSnapshotText(t)');
d.rows.forEach(r=>console.log(r.cat,r.name,'q=',r.qty,'cur=',r.cur,'avg=',r.avg));
const s4=d.rows.find(r=>r.name==='삼성전자');
ok(s4&&s4.qty===9&&s4.cur===257500&&s4.avg===295790,'삼성전자 컬럼 추정');
const lg=d.rows.find(r=>r.name==='LG전자');
ok(lg&&Math.abs(lg.qty-8.003564)<1e-6&&lg.cur===200000&&lg.avg===186237,'LG전자 소수수량');
const st=d.rows.find(r=>r.name==='에스티팜');
ok(st&&st.qty===70&&st.cur===110600&&st.avg===100236,'에스티팜');
const bora=d.rows.find(r=>r.name==='BORA');
ok(bora&&bora.cat==='crypto'&&Math.abs(bora.qty-1920.043087)<1e-6&&bora.cur===28.4&&bora.avg===490.3,'BORA 코인: '+JSON.stringify(bora));
ok(!d.rows.find(r=>r.name==='종목명'),'헤더 라인 제외');
// 코인이 본문에 있으므로 본문에 빠진 다른 코인이 missing으로 잡히는지
ok(d.missing.some(m=>m.entry.cat==='crypto'),'코인 missing 감지');

// 월 배분: 모든 자산이 목표 충족이면 비례 적립으로 전액 배분
run('portfolio.targets={kr:0,us:0,bonds:0,gold:0,crypto:0}');
let p=run('newMoneyPlan(1000000)');
let sum=p.allocs.reduce((s,a)=>s+a.amt,0);
ok(Math.abs(sum)<1,'목표 0이면 배분 0');
run('portfolio.targets={kr:25,us:25,bonds:20,gold:20,crypto:10}');

// regime 프리셋 적용
run('applyRegimeTargets && (overallSignal())');
// bull 강제
run("portfolio.switching.retail=[{ym:'2026-01',val:1},{ym:'2026-02',val:2},{ym:'2026-03',val:3},{ym:'2026-04',val:4},{ym:'2026-05',val:5}];");
run("portfolio.switching.ism=[{ym:'2026-01',val:50},{ym:'2026-02',val:60},{ym:'2026-03',val:70},{ym:'2026-04',val:80},{ym:'2026-05',val:90}];");
ok(run('overallSignal().s')==='bull','bull 강제 성공: '+run('overallSignal().s'));
run('applyRegimeTargets()');
ok(run('portfolio.targets.bonds')===12,'강세 프리셋 채권 12%');
ok(run('portfolio.targets.crypto')===18,'강세 프리셋 코인 18%');
p=run('newMoneyPlan(2000000)');
sum=p.allocs.reduce((s,a)=>s+a.amt,0);
ok(Math.abs(sum-2000000)<2,'강세 프리셋에서도 월 200만 전액 배분: '+sum);
console.log(p.allocs.map(a=>a.name+' '+(a.amt/10000).toFixed(1)+'만').join(', '));

// 매수 후 평단 검증: s4 현재 q9.058985 avg295790, 1주 260000 매수
run("const h=portfolio.holdings.kr_stocks.find(x=>x.id==='s4');const b=h.qty;const a=h.avg;applyTrade(h,'kr','buy',1,260000,0,'2026-09-10');globalCheck=[h.qty,h.avg,(b*a+260000)/(b+1)];");
const got=run('globalCheck');
ok(Math.abs(got[1]-got[2])<1e-6,'평단 가중평균 정확');

console.log(pass+' passed, '+fail+' failed');
process.exit(fail?1:0);
