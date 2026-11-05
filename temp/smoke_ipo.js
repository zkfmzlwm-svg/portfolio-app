// 단타 탭 🆕 신규상장 모의매매(v6.8) 회귀 테스트: 호가·지정가·익절가, 체결·청산 판정, 38 파싱, 갱신 흐름(시각 조건), 화면
const fs=require('fs'),vm=require('vm'),path=require('path');
const html=fs.readFileSync(path.join(__dirname,'../app/src/main/assets/index.html'),'utf8');
const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const vals={},els={};
const mkEl=id=>({id,style:{},_html:'',set innerHTML(v){this._html=v;},get innerHTML(){return this._html;},
  get value(){return vals[id]??'';},set value(v){vals[id]=v;},addEventListener(){},focus(){},blur(){},querySelector(){return mkEl('q');}});
const alerts=[];
const sandbox={console,window:{},localStorage:{_d:{},getItem(k){return this._d[k]??null;},setItem(k,v){this._d[k]=v;}},
  document:{getElementById(id){els[id]=els[id]||mkEl(id);return els[id];},addEventListener(){},querySelector:()=>mkEl('q'),querySelectorAll:()=>[]},
  alert:m=>alerts.push(m),confirm:()=>true,setTimeout:()=>0,clearTimeout(){},Date,Math,JSON,isNaN,parseFloat,parseInt,Object,Array,Set,Map,String,Number,RegExp,Error,Promise};
vm.createContext(sandbox);vm.runInContext(code,sandbox);
const run=e=>vm.runInContext(e,sandbox);
let pass=0,fail=0;
const ok=(c,m)=>{if(c)pass++;else{fail++;console.log('✗ FAIL:',m);}};
const near=(a,b,e=1e-12)=>Math.abs(a-b)<e;
const clean=s=>!/undefined|NaN|\[object/.test(s);
// 한국 시각 고정: kstNow()는 UTC 필드로 읽는 Date
const setNow=(ymd,hh,mm)=>run(`kstNow=()=>new Date(Date.UTC(${+ymd.slice(0,4)},${+ymd.slice(5,7)-1},${+ymd.slice(8,10)},${hh},${mm}))`);

(async()=>{
// 1. 지정가·익절가·호가
ok(run('ipoLimit(12000,1.5)')===18000&&run('ipoLimit(15500,1.5)')===23250&&run('ipoLimit(13300,1.5)')===19950&&run('ipoLimit(3300,1.5)')===4950,'지정가 = 공모가 × N 호가 내림');
ok(run('ipoLimit(12345,1.5)')===18510,'지정가 호가 내림 (18,517.5 → 18,510)');
ok(run('ipoTarget(19950,13300,2)')===20350&&run('ipoNeed(20350,13300)')===20400,'익절가 호가 올림 + 보수 체결 1호가');
ok(run('ipoTarget(39500,10000,2)')===40000&&run('ipoNeed(40000,10000)')===40000,'익절가가 상한가(공모가 × 4)를 넘으면 상한가, 상한가는 +1호가 없이');

// 2. 체결·청산 판정
const it={d:'2026-11-04',code:'495910',name:'이에스티',offer:12400};
sandbox.__it=it;
const opt=`{n:1.5,x:2,exit:'t10',fee:0.015,amt:1000000}`;
let t=run(`ipoSettle(__it,{o:19000,h:21000,l:15000,c:15000},null,${opt})`);
ok(t.fill===false&&/1\.53배 > 1\.5배/.test(t.why)&&t.lim===18600,'시초가 > 지정가 → 미체결');
t=run(`ipoSettle(__it,{o:49600,h:49600,l:49600,c:49600},null,{n:4,x:2,exit:'t10',fee:0.015})`);
ok(t.fill===false&&t.why==='상한가 시작','시초가 = 상한가 → 미체결');
t=run(`ipoSettle(__it,{o:15890,h:20700,l:9900,c:9940},{src:'1m',open:15890,bars:[{h:20000,c:19750},{h:20700,c:18780},{h:16000,c:15920}]},${opt})`);
ok(t.fill&&t.ent===15890&&t.tgt===16210&&t.xp===16210&&t.how==='tp'&&t.src==='1m','1분봉: 시초가 15,890 → +2% 16,210 익절');
ok(near(t.ret,run('dtNetRet(15890,16210,false,0.015)'))&&near(t.ret,16210*(1-0.00015-0.002)/(15890*1.00015)-1),'순수익: 수수료·거래세 0.20%');
t=run(`ipoSettle(__it,{o:15890,h:30000,l:9900,c:9940},{src:'60m',open:15890,bars:[{h:16210,c:15000}]},${opt})`);
ok(t.fill&&t.how==='t10'&&t.xp===15000&&t.src==='60m','고가 = 목표가(1호가 못 넘음) → 10시 시장가 매도 (일봉 고가는 무시)');
t=run(`ipoSettle(__it,{o:15890,h:16220,l:9900,c:9940},null,${opt})`);
ok(t.fill&&t.how==='tp'&&t.src==='1d','분봉 없음 → 일봉 근사(고가 ≥ 목표 + 1호가면 익절)');
t=run(`ipoSettle(__it,{o:15890,h:16210,l:9900,c:9940},null,{n:1.5,x:2,exit:'close',fee:0.015})`);
ok(t.fill&&t.how==='close'&&t.xp===9940&&near(t.ret,run('dtNetRet(15890,9940,false,0.015)')),'당일 종가 모드: 못 팔면 종가');
t=run(`ipoSettle(__it,{o:12400,h:13000,l:12000,c:12100},null,{n:1.0,x:2,exit:'close',fee:0.015})`);
ok(t.fill&&t.ent===12400&&t.lim===12400,'시초가 = 지정가 → 체결');

// 2-2. 익절 +3%·손절 −3% 동시 주문 (시초가 15,890 → 익절 16,370(체결 조건 16,380) · 손절 15,410(체결 15,400))
const br=`{n:1.5,x:3,sl:3,exit:'t10',fee:0.015,amt:1000000}`;
ok(run('ipoStop(15890,3)')===15410&&run('ipoTarget(15890,12400,3)')===16370,'손절가 호가 내림 · 익절가 호가 올림');
t=run(`ipoSettle(__it,{o:15890,h:21000,l:9000,c:9940},{src:'1m',open:15890,bars:[{o:15890,h:20000,l:15790,c:19750},{o:19750,h:20700,l:9000,c:9000}]},${br})`);
ok(t.how==='tp'&&t.xp===16370&&!t.amb&&t.stop===15410&&t.sl===3,'익절가가 먼저 → 익절 (뒤 봉 급락은 무관)');
t=run(`ipoSettle(__it,{o:15890,h:21000,l:9000,c:9940},{src:'1m',open:15890,bars:[{o:15890,h:16000,l:15300,c:15500},{o:15500,h:17000,l:15400,c:16900}]},${br})`);
ok(t.how==='sl'&&t.xp===15400&&!t.amb&&near(t.ret,run('dtNetRet(15890,15400,false,0.015)')),'손절가가 먼저 → 손절가 − 1호가(15,400)');
t=run(`ipoSettle(__it,{o:15890,h:21000,l:9000,c:9940},{src:'1m',open:15890,bars:[{o:15890,h:17000,l:15000,c:16000}]},${br})`);
ok(t.how==='sl'&&t.amb===true&&t.xp===15400&&near(t.retOpt,run('dtNetRet(15890,16370,false,0.015)')),'같은 봉 둘 다 → 손절로 기록 + 익절이었을 값(retOpt)');
t=run(`ipoSettle(__it,{o:15890,h:21000,l:9000,c:9940},{src:'1m',open:15890,bars:[{o:15890,h:16100,l:15600,c:15600},{o:15200,h:15300,l:15100,c:15200}]},${br})`);
ok(t.how==='sl'&&t.xp===15190,'다음 봉이 손절가 아래에서 시작(갭) → 그 시가 − 1호가');
t=run(`ipoSettle(__it,{o:15890,h:21000,l:9000,c:9940},{src:'1m',open:15890,bars:[{o:15890,h:16300,l:15500,c:16000},{o:16000,h:16200,l:15600,c:15900}]},${br})`);
ok(t.how==='t10'&&t.xp===15900,'10:00까지 둘 다 안 닿음 → 10시 시장가');
t=run(`ipoSettle(__it,{o:15890,h:20700,l:9900,c:9940},null,${br})`);
ok(t.how==='sl'&&t.amb&&t.src==='1d','일봉 근사: 고가·저가 둘 다 닿으면 손절로 기록(순서 불명)');
t=run(`ipoSettle(__it,{o:15890,h:20700,l:15500,c:16000},null,${br})`);
ok(t.how==='tp'&&!t.amb,'일봉: 저가가 손절가 위면 익절');
t=run(`ipoSettle(__it,{o:39500,h:40000,l:39000,c:39800},null,{n:4,x:3,sl:3,exit:'close',fee:0.015})`);
ok(t.fill===false||t.tgt<=12400*4,'익절가는 상한가 이하');

// 3. 38커뮤니케이션 표 파싱 (예정·스팩·리츠·코드 없음)
const row=(n,d,offer,code)=>`<tr bgColor="#FFFFFF"><td height=30><a href="./?o=v&amp;no=1"><font color="0066CC">${n}</font></a></td><td align="center">${d}</td><td>-&nbsp;</td><td>%</td><td align="RIGHT">${offer}&nbsp;</td><td>-%</td><td>-&nbsp;</td><td>%</td><td>예정&nbsp;</td><td>${code?`<a href='/chart/chart_page_new.php3?code=${code}'>`:''}</td></tr>`;
sandbox.__h=`<table summary="신규상장종목"><thead><tr><th>기업명</th></tr></thead><tbody>${row('옵토닉스','2026/11/17','12,000','493260')}${row('아이엠스팩1호','2026/11/04','2,000','0222E0')}${row('삼성FN리츠(유가)','2026/11/03','5,000','448730')}${row('코드없음','2026/11/02','9,000','')}${row('래블업','2026/11/03','19,000','0147B0')}</tbody></table><table>`;
const cal=run('ipoParse38(__h)');
ok(cal.length===4&&cal[0].d==='2026-11-17'&&cal[0].offer===12000&&cal[0].code==='493260'&&!cal[0].spac,'표 파싱: 날짜·공모가·코드');
ok(cal[1].spac===true&&cal[2].reit===true&&cal[3].code==='0147B0'&&!cal.some(x=>x.name==='코드없음'),'스팩·리츠 표시, 코드 없는 줄 제외');
ok(run("ipoParse38('<html>점검 중</html>')").length===0,'표 없으면 빈 목록');

// 4. 갱신 흐름 — 상장일 시각 조건, 1분봉 → 60분봉 → 일봉 근사, 스팩 제외, 중복 없음
run("portfolio.dt=JSON.parse(JSON.stringify(DT_DEFAULT));portfolio.dt.start='2026-10-01';delete portfolio.dt.ipo;tab='home'");
sandbox.__calls=[];
sandbox.__minute={};sandbox.__hour={};
sandbox.__days={'495910':{d:'2026-11-04',o:15890,h:20700,l:9900,c:9940},'0147B0':{d:'2026-11-03',o:19000,h:22200,l:13000,c:14170},'0222E0':{d:'2026-11-04',o:2580,h:2600,l:1800,c:1861},'111111':{d:'2026-10-20',o:10000,h:12000,l:8000,c:8500}};
run(`nativeGetText=async u=>{__calls.push(u);return u.endsWith('page=1')?__h38:'';}`);
sandbox.__h38=`<table summary="신규상장종목">${row('옵토닉스','2026/11/17','12,000','493260')}${row('이에스티','2026/11/04','12,400','495910')}${row('아이엠스팩1호','2026/11/04','2,000','0222E0')}${row('래블업','2026/11/03','19,000','0147B0')}${row('오래된종목','2026/10/20','8,000','111111')}${row('시작전','2026/09/01','8,000','222222')}</table>`;
run(`dtFetchCandles=async(c,from)=>__days[c]?[__days[c]]:[]`);
run(`nativeGet=async u=>{__calls.push(u);if(/minute/.test(u)){const c=u.match(/item\\/(\\w+)\\//)[1];return __minute[c]||[];}if(/yahoo/.test(u)){const c=u.match(/chart\\/(\\w+)\\./)[1];return __hour[c]||{chart:{result:null}};}return null;}`);
const mb=(ymd,hm,o,h,c)=>({localDateTime:ymd+hm+'00',openPrice:o,highPrice:h,lowPrice:Math.min(o,c),currentPrice:c});
sandbox.__minute['495910']=[mb('20261104','0900',15890,20000,19750),mb('20261104','0901',19750,20700,18780),mb('20261104','0930',16000,16100,16000)];   // 09:59 전 (아직 부분)
sandbox.__minute['0147B0']=[mb('20261103','0900',19000,19300,19100),mb('20261103','0959',18000,18200,17900),mb('20261103','1000',17900,17950,17800)];
// 2026-11-04 09:30 — 오늘 상장(이에스티)은 10:01 전이라 대기, 어제 상장(래블업)은 1분봉으로 확정
setNow('2026-11-04',9,30);
await run('ipoRefresh(true)');
let s=run('ipoState()');
ok(s.start==='2026-10-05'&&s.cal.length===6&&s.calAt>0,'처음 켤 때 최근 30일부터 · 일정 저장');
ok(s.trades.length===2&&s.trades.map(x=>x.code).sort().join()==='0147B0,111111','09:30: 어제·지난 상장만 확정, 오늘 상장 대기, 스팩·시작일 이전 제외');
const lb=s.trades.find(x=>x.code==='0147B0');
ok(lb.fill&&lb.ent===19000&&lb.tgt===19570&&lb.stop===18430&&lb.how==='sl'&&lb.xp===17990&&lb.src==='1m','래블업: 익절 19,570 못 닿고 09:59 봉이 18,000(손절가 18,430 아래)에서 시작 → 17,990 손절');
const old=s.trades.find(x=>x.code==='111111');
ok(old.fill&&old.src==='1d'&&old.how==='sl'&&old.amb&&old.xp===9690&&near(old.retOpt,run('dtNetRet(10000,10300,false,0.015)')),'1분봉·60분봉 없는 지난 종목 → 일봉 근사(둘 다 닿음 → 손절로 기록)');
// 10:05 — 오늘 1분봉이 09:59까지 들어오면 확정
sandbox.__minute['495910'].push(mb('20261104','0959',15950,16000,15920));
setNow('2026-11-04',10,5);
await run('ipoRefresh(true)');
s=run('ipoState()');
const es=s.trades.find(x=>x.code==='495910');
ok(s.trades.length===3&&es&&es.fill&&es.how==='tp'&&es.tgt===16370&&!es.amb&&es.src==='1m','10:05: 오늘 상장 이에스티 1분봉으로 익절 확정(첫 분 저가 15,890 > 손절가)');
await run('ipoRefresh(true)');ok(run('ipoState().trades.length')===3,'다시 갱신해도 중복 없음');
// 60분봉 대체: 1분봉 없는 날
run("portfolio.dt.ipo.trades=portfolio.dt.ipo.trades.filter(x=>x.code!=='0147B0')");
delete sandbox.__minute['0147B0'];
const ts=Math.floor(Date.UTC(2026,10,3,0,0)/1000);   // 09:00 KST
sandbox.__hour['0147B0']={chart:{result:[{timestamp:[ts-86400,ts],indicators:{quote:[{open:[1,19000],high:[1,19600],low:[1,18800],close:[1,19100]}]}}]}};
await run('ipoRefresh(true)');
const lb2=run("ipoState().trades.find(x=>x.code==='0147B0')");
ok(lb2&&lb2.src==='60m'&&lb2.how==='tp'&&lb2.xp===19570,'1분봉 없으면 야후 60분봉 첫 봉(고가 19,600 ≥ 19,580, 저가 18,800 > 손절가) 익절');
// 시가가 일봉과 다른 60분봉은 버리고 일봉 근사
run("portfolio.dt.ipo.trades=portfolio.dt.ipo.trades.filter(x=>x.code!=='0147B0')");
sandbox.__hour['0147B0'].chart.result[0].indicators.quote[0].open[1]=18000;
await run('ipoRefresh(true)');
ok(run("ipoState().trades.find(x=>x.code==='0147B0').src")==='1d','60분봉 시가 불일치 → 일봉 근사');
// 당일 종가 모드: 15:40 전엔 오늘 상장 대기
run("portfolio.dt.ipo.trades=portfolio.dt.ipo.trades.filter(x=>x.code!=='495910');portfolio.dt.ipo.exit='close'");
setNow('2026-11-04',15,0);await run('ipoRefresh(true)');
ok(!run("ipoState().trades.some(x=>x.code==='495910')"),'종가 모드: 15:40 전 대기');
setNow('2026-11-04',15,45);await run('ipoRefresh(true)');
const ec=run("ipoState().trades.find(x=>x.code==='495910')");
ok(ec&&ec.exit==='close'&&ec.how==='sl'&&ec.amb&&ec.src==='1d','종가 모드: 15:45 확정(일봉 — 둘 다 닿아 손절로 기록)');
run("portfolio.dt.ipo.exit='t10'");
// 끄면 갱신 안 함
sandbox.__calls.length=0;run("portfolio.dt.ipo.on=false");await run('ipoRefresh(true)');
ok(sandbox.__calls.length===0,'끄면 네트워크 요청 없음');run("portfolio.dt.ipo.on=true");
// 일정 실패해도 기존 일정 유지
run(`nativeGetText=async u=>{throw new Error('x')}`);await run('ipoRefresh(true)');
ok(run('ipoState().cal.length')===6&&/불러오지 못했습니다/.test(run('ipoErr')),'일정 실패: 오류 표시 · 기존 일정 유지');

// 5. 통계·화면
setNow('2026-11-05',8,40);
const st=run('ipoStats(ipoState().trades)');
ok(st.n===3&&st.nofill===0&&st.tp===0&&st.slr===1&&st.amb===3&&st.avgOpt>st.avg&&clean(JSON.stringify(st)),'통계: 익절·손절률 · 동시 도달 건수 · 낙관 평균');
run("ipoErr=null");
const sc=run('ipoSignalCard()');
ok(clean(sc)&&sc.includes('모의매매 전용')&&sc.includes('옵토닉스')&&sc.includes('지정가 18,000')&&!sc.includes('아이엠스팩')&&!sc.includes('dtOrder'),'신호 화면: 다가오는 상장 · 지정가 · 스팩 제외 · 주문 버튼 없음');
const pv=run('ipoPaperView()');
ok(clean(pv)&&pv.includes('신규상장 모의매매')&&pv.includes('래블업')&&pv.includes('손절')&&pv.includes('일봉 근사')&&pv.includes('손절로 셌습니다')&&pv.includes('−3% 손절 동시 주문')&&pv.includes('백테스트 기대치'),'모의매매 화면: 장부·출처·동시 도달 안내');
const cf=run('ipoCfgCard()');
ok(clean(cf)&&cf.includes('dtIpoN')&&cf.includes('dtIpoS')&&cf.includes('value="3"')&&cf.includes('10:00 시장가 (권장)'),'설정 카드: 익절·손절 입력');
run("dtSub='paper';tab='daytrade';render()");ok(clean(run("document.getElementById('app').innerHTML")),'단타 탭 모의매매 렌더');
run("dtSub='signal';render()");ok(clean(run("document.getElementById('app').innerHTML")),'단타 탭 신호 렌더');
run("dtSub='cfg';render()");const cfgHtml=run("document.getElementById('app').innerHTML");ok(clean(cfgHtml)&&cfgHtml.includes('모의 전용'),'단타 탭 설정 렌더');
// 설정 저장·검증
const setv=(n,x,sl)=>{sandbox.document.getElementById('dtIpoN').value=n;sandbox.document.getElementById('dtIpoX').value=x;sandbox.document.getElementById('dtIpoS').value=sl;};
setv('5','3','3');alerts.length=0;run('ipoSaveNum()');ok(alerts.length===1&&run('ipoState().n')===1.5,'N 범위 밖(5) 거부');
setv('1.5','3','45');alerts.length=0;run('ipoSaveNum()');ok(alerts.length===1&&run('ipoState().sl')===3,'손절 40% 이상 거부');
setv('1.2','4','2.5');run('ipoSaveNum()');ok(run('ipoState().n')===1.2&&run('ipoState().x')===4&&run('ipoState().sl')===2.5,'N·익절·손절 저장');
setv('1.2','4','0');run('ipoSaveNum()');ok(run('ipoState().sl')===0&&run('ipoRuleText(ipoState())').includes('손절 없음'),'손절 0 = 없음');
run("ipoSet('exit','close')");ok(run('ipoState().exit')==='close','청산 방식 저장');
run("ipoSet('on','0')");ok(run('ipoState().on')===false&&run('ipoSignalCard()')==='','끄기 → 신호 카드 숨김');
// 저장·복원: portfolio JSON에 포함
ok(JSON.parse(sandbox.localStorage._d.porto).dt.ipo.trades.length===3,'기록이 저장소에 남음');
run("ipoReset()");ok(run('ipoState().trades.length')===0&&run('ipoState().start')==='2026-10-06','초기화: 기록 삭제 · 최근 30일부터');

// 6. v6.8 내부 교체: 익절만(+2%) 쓰던 상태 → 익절 +3%·손절 −3%, 기록 다시 계산(1회)
run("portfolio.dt.ipo={on:true,n:1.5,x:2,exit:'t10',start:'2026-09-01',cal:[],calAt:0,trades:[{key:'a|2026-10-01',fill:true,ret:0.01}]}");
let ms=run('ipoState()');
ok(ms.x===3&&ms.sl===3&&ms.trades.length===0&&ms.start==='2026-10-06'&&ms.bracketV1===true,'익절만 쓰던 상태 → ±3%로 교체 · 기록 비우고 최근 30일부터');
run("portfolio.dt.ipo.x=5;portfolio.dt.ipo.sl=0");ms=run('ipoState()');ok(ms.x===5&&ms.sl===0,'교체 후 사용자가 바꾼 값(손절 0 포함)은 유지');
ok(run("JSON.parse(JSON.stringify(IPO_DEFAULT)).x")===3&&run("IPO_DEFAULT.sl")===3,'기본값 ±3%');

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail?1:0);
})();
