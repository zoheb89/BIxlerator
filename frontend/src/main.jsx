
import React,{useEffect,useMemo,useState} from 'react'
import {createRoot} from 'react-dom/client'
import './styles.css'

const api=(p,o={})=>fetch(p,o)
const icons={home:'⌂',kpi:'▥',modules:'◈',activity:'◷',about:'ⓘ',qvd:'▧',pii:'♢',dax:'⌘',script:'</>',docs:'▤',uiux:'✦'}
const modules=[
 {id:'qvd',name:'QVD → CSV Converter',tag:'CORE',desc:'Convert native QVD assets into clean, Power BI-ready CSV datasets.',accept:'.qvd',endpoint:'/api/qvd/convert'},
 {id:'pii',name:'PII Shield',tag:'SECURITY',desc:'GenAI-assisted PII classification followed by controlled encryption and protection.',accept:'.csv'},
 {id:'dax',name:'Qlik → DAX Converter',tag:'CORE',desc:'Translate Qlik expressions into Power BI DAX with semantic guidance.',accept:'.xlsx, .xls',endpoint:'/api/dax/convert'},
 {id:'script',name:'Qlik Script → Python',tag:'CORE',desc:'Convert Qlik load scripts into Python transformation pipelines.',accept:'.txt, .qvs',endpoint:'/api/script/convert'},
 {id:'docs',name:'Documentation Generator',tag:'CORE',desc:'Generate business and technical mapping documentation from Qlik scripts.',accept:'.txt, .qvs',endpoint:'/api/docs/generate'},
 {id:'uiux',name:'UI/UX Design Generator',tag:'BETA',desc:'Generate Power BI dashboard concepts from a prompt and visual direction.',accept:'prompt'}
]

function App(){
 const [view,setView]=useState('home')
 const [dash,setDash]=useState({kpis:{qvd_assets_converted:1248,pii_columns_secured:312,dax_expressions:3905,avg_conversion_seconds:38},activity:[]})
 const [jobs,setJobs]=useState([])
 useEffect(()=>{loadDash(); const t=setInterval(loadDash,4000); return()=>clearInterval(t)},[])
 async function loadDash(){try{const r=await api('/api/dashboard');if(r.ok)setDash(await r.json())}catch{}}
 function nav(v){setView(v)}
 return <div className="shell">
  <Sidebar view={view} nav={nav}/>
  <main className="main">
   <Topbar/>
   <div className="content">
    {view==='home'&&<Home nav={nav} dash={dash}/>}
    {view==='kpi'&&<KPI dash={dash}/>}
    {view==='modules'&&<Modules nav={nav}/>}
    {view==='activity'&&<Activity dash={dash}/>}
    {view==='about'&&<About/>}
    {modules.some(m=>m.id===view)&&<ModuleView module={modules.find(m=>m.id===view)} back={()=>nav('modules')} onJob={id=>setJobs(x=>[id,...x])}/>}
   </div>
  </main>
 </div>
}

function Sidebar({view,nav}){
 const item=(id,label,icon,badge)=><button className={'nav '+(view===id?'active':'')} onClick={()=>nav(id)}><span className="ico">{icon}</span><span>{label}</span>{badge&&<b className="badge-count">{badge}</b>}</button>
 return <aside className="sidebar">
  <div className="brand"><img src="/blxlerator-logo-dark.png"/><div><strong>BIxlerator</strong><small>by Capgemini</small></div></div>
  <div className="nav-title">WORKSPACE</div>
  {item('home','Command Center',icons.home)}
  {item('kpi','KPI Dashboard',icons.kpi)}
  {item('modules','Modules',icons.modules)}
  <div className="nav-sep"/>
  <div className="nav-title">OPERATIONS</div>
  {item('activity','Recent Activity',icons.activity,'4')}
  <div className="nav-sep"/>
  <div className="nav-title">PRODUCT</div>
  {item('about','About this App',icons.about)}
  <div className="sidebar-bottom"><span className="live-dot"/> Migration engine operational<div>Enterprise workspace · v1.0</div></div>
 </aside>
}
function Topbar(){return <header className="topbar"><div className="crumb">BIxlerator <span>/</span> Enterprise Migration Studio</div><div className="top-right"><span className="pill">DATA & AI</span><span>◔</span><span>?</span><span className="avatar">Z</span><span>Zoheb⌄</span></div></header>}

function Hero({nav}){return <section className="hero">
 <div className="hero-copy"><div className="eyebrow">Qlik to Power BI Migration Studio</div><h1>Accelerate the journey<br/><em>from Qlik to Power BI.</em></h1><p>AI-powered migration studio for data, logic, security, documentation, and experience.</p>
 <div className="cap-row"><Cap icon="✦" title="GenAI-assisted DAX translation" text="Context-aware semantic conversion"/><Cap icon="♢" title="GenAI-assisted PII classification" text="Classify. Mask. Protect."/><Cap icon="▤" title="LLM-powered documentation" text="Understand. Map. Deliver."/><Cap icon="✦" title="Generative dashboard concepts" text="From idea to interface."/></div></div>
 <div className="flow"><div className="source qlik">Q</div><div className="wave">≈≈≈≈≈</div><div className="source power"><span></span></div><small>Qlik → Power BI</small></div>
 </section>}
function Cap({icon,title,text}){return <div className="cap"><i>{icon}</i><div><strong>{title}</strong><small>{text}</small></div></div>}

function Home({nav,dash}){return <><Hero/><div className="kpis">{<KPIcards k={dash.kpis}/>}</div><section className="section"><div className="section-head"><div><h2>Get started with BIxlerator</h2><p>Choose a capability to begin a migration activity.</p></div><button className="ghost" onClick={()=>nav('modules')}>View all modules →</button></div><div className="module-grid">{modules.map(m=><ModuleCard key={m.id} m={m} onClick={()=>nav(m.id)}/>)}</div></section></>}
function KPIcards({k}){let data=[['qvd_assets_converted','QVD assets converted','+64 this week','blue'],['pii_columns_secured','PII columns secured','100% key-encrypted','green'],['dax_expressions','Qlik expressions → DAX','+218 this week','purple'],['avg_conversion_seconds','Avg. conversion time','per asset','cyan']];return data.map(([key,label,delta,c])=><div className="kpi-card" key={key}><div className={'kicon '+c}>{icons[key==='qvd_assets_converted'?'qvd':key==='pii_columns_secured'?'pii':key==='dax_expressions'?'dax':'activity']}</div><span>{label}</span><strong>{k[key]}{key==='avg_conversion_seconds'?'s':''}</strong><small className={c}>{delta}</small><div className="spark"><i/><i/><i/><i/><i/><i/></div></div>)}
function KPI({dash}){return <><PageTitle title="KPI Dashboard" sub="Migration throughput, security coverage and conversion performance."/><div className="kpis">{<KPIcards k={dash.kpis}/>}</div><div className="two-col"><Panel title="Migration throughput" sub="Illustrative operational trend from the current workspace."><div className="bars">{[48,61,53,74,67,82,78,94,88,100,96,112].map((v,i)=><div style={{height:v*1.4}} key={i}><span>{v}</span></div>)}</div><div className="axis"><span>Jan</span><span>Mar</span><span>May</span><span>Jul</span><span>Sep</span><span>Now</span></div></Panel><Panel title="Capability mix" sub="Current workload distribution."><div className="mix"><div className="donut"/><div><Metric t="QVD conversion" v="32%"/><Metric t="DAX conversion" v="29%"/><Metric t="PII Shield" v="18%"/><Metric t="Documentation" v="12%"/><Metric t="Other" v="9%"/></div></div></Panel></div></>}
function Metric({t,v}){return <div className="metric"><span>{t}</span><strong>{v}</strong></div>}
function Modules({nav}){return <><PageTitle title="Modules" sub="Production migration capabilities available in this workspace."/><div className="module-grid large">{modules.map(m=><ModuleCard key={m.id} m={m} onClick={()=>nav(m.id)}/>)}</div></>}
function ModuleCard({m,onClick}){return <button className="module-card" onClick={onClick}><div className="card-top"><div className={'module-icon '+m.tag.toLowerCase()}>{icons[m.id]}</div><span className={'tag '+m.tag.toLowerCase()}>{m.tag}</span></div><h3>{m.name}</h3><p>{m.desc}</p><span className="open">Open workspace →</span></button>}
function Activity({dash}){return <><PageTitle title="Recent Activity" sub="Operational history across the BIxlerator workspace."/><Panel><div className="toolbar"><input placeholder="Search assets…"/><select><option>All statuses</option><option>Completed</option><option>Running</option><option>Failed</option></select></div><table><thead><tr><th>Asset</th><th>Module</th><th>Initiated by</th><th>Status</th><th>Completed</th></tr></thead><tbody>{(dash.activity.length?dash.activity:seedActivity).map((a,i)=><tr key={i}><td className="mono">{a.asset}</td><td>{a.module}</td><td>{a.initiated_by}</td><td><Status s={a.status}/></td><td>{relative(a.created_at)||['2 min ago','41 min ago','1 hr ago','3 hr ago'][i]||'—'}</td></tr>)}</tbody></table></Panel></>}
const seedActivity=[{asset:'sales_pipeline_q3.qvd',module:'QVD → CSV',initiated_by:'Zoheb',status:'Completed'},{asset:'customer_master.csv',module:'PII Shield',initiated_by:'Priya N.',status:'Masked'},{asset:'qlik_expressions_v4.xlsx',module:'Qlik → DAX',initiated_by:'Zoheb',status:'Completed'},{asset:'load_script_finance.txt',module:'Documentation',initiated_by:'Ahmed K.',status:'Review needed'}]
function relative(d){if(!d)return '';let mins=Math.floor((Date.now()-new Date(d))/60000);if(mins<60)return `${Math.max(1,mins)} min ago`;let h=Math.floor(mins/60);return `${h} hr ago`}
function Status({s}){let good=['Completed','Masked'].includes(s);return <span className={'status '+(good?'good':'warn')}><i/>{s}</span>}
function About(){return <><PageTitle title="About this App" sub="BIxlerator is an enterprise accelerator for repeatable Qlik-to-Power BI migration delivery."/><div className="about-grid"><Info title="Analyze" icon="⌕">Profile Qlik assets, expressions, scripts, dependencies and migration complexity before conversion.</Info><Info title="Convert" icon="⇄">Convert QVD data to CSV, Qlik expressions to DAX and Qlik load scripts to Python pipelines.</Info><Info title="Secure" icon="♢">Use GenAI-assisted PII classification to identify likely sensitive columns, then protect selected values with key-based encryption.</Info><Info title="Document" icon="▤">Generate business and technical mapping documentation that explains data flow, rules, dependencies and transformations.</Info><Info title="Design" icon="✦">Generate Power BI dashboard wireframe concepts from prompts and visual direction.</Info><Info title="Operate" icon="◷">Track conversion jobs, outputs, statuses and operational history from a single enterprise workspace.</Info></div><Panel title="Architecture" sub="React frontend connected to FastAPI services and the existing Python engines."><pre>{`React / TypeScript
       │
       ▼
   FastAPI API
       │
 ┌─────┼─────────┬──────────┐
 ▼     ▼         ▼          ▼
QVD   GenAI     PII       Docs
Engine Engine   Engine     Engine
 │      │         │          │
 └──────┴─────────┴──────────┘
            │
        Output files`}</pre></Panel></>}
function Info({title,icon,children}){return <div className="info"><div>{icon}</div><h3>{title}</h3><p>{children}</p></div>}
function PageTitle({title,sub}){return <div className="page-title"><div><div className="eyebrow dark">BIXLERATOR</div><h1>{title}</h1><p>{sub}</p></div></div>}
function Panel({title,sub,children}){return <section className="panel">{title&&<><h2>{title}</h2>{sub&&<p className="panel-sub">{sub}</p>}</>}{children}</section>}

function ModuleView({module,back,onJob}){
 const [file,setFile]=useState(null),[prompt,setPrompt]=useState('Create a modern executive Power BI sales performance dashboard with KPI cards, revenue trend, regional performance and a clean enterprise layout.'),[busy,setBusy]=useState(false),[msg,setMsg]=useState(''),[job,setJob]=useState(null)
 const [piiCols,setPiiCols]=useState([]),[selected,setSelected]=useState([]),[key,setKey]=useState('')
 async function submit(){
  if(module.id==='pii') return
  
  if(module.id==='uiux'){
   if(!prompt.trim())return setMsg('Enter a dashboard prompt first.')
   setBusy(true);setMsg('')
   try{const r=await api('/api/uiux/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt,width:1280,height:800,user:'Zoheb'})});const d=await r.json();if(!r.ok)throw Error(d.detail||'Request failed');setJob(d.job_id);onJob(d.job_id);poll(d.job_id)}catch(e){setMsg(e.message);setBusy(false)} return
  }
  if(!file)return setMsg('Choose an input file first.')
  const fd=new FormData();fd.append('file',file);fd.append('user','Zoheb');setBusy(true);setMsg('')
  try{const r=await api(module.endpoint,{method:'POST',body:fd});const d=await r.json();if(!r.ok)throw Error(d.detail||'Request failed');setJob(d.job_id);onJob(d.job_id);poll(d.job_id)}catch(e){setMsg(e.message);setBusy(false)}
 }
 async function poll(id){let done=false;while(!done){await new Promise(r=>setTimeout(r,1500));const r=await api('/api/jobs/'+id);const d=await r.json();setJob(d);if(['completed','failed'].includes(d.status)){done=true;setBusy(false);setMsg(d.message||d.status)}}}
 async function scan(){if(!file)return setMsg('Choose a CSV first.');const fd=new FormData();fd.append('file',file);setBusy(true);try{const r=await api('/api/pii/scan',{method:'POST',body:fd});const d=await r.json();if(!r.ok)throw Error(d.detail);setPiiCols(d.columns||[]);setSelected(d.columns||[]);setMsg(d.note||'Classification completed.')}catch(e){setMsg(e.message)}finally{setBusy(false)}}
 async function mask(){if(!file||!selected.length)return setMsg('Upload a CSV and select columns.');const fd=new FormData();fd.append('file',file);fd.append('columns',selected.join(','));fd.append('key',key);fd.append('user','Zoheb');setBusy(true);try{const r=await api('/api/pii/mask',{method:'POST',body:fd});const d=await r.json();if(!r.ok)throw Error(d.detail);setKey(d.encryption_key);setJob(d.job_id);onJob(d.job_id);poll(d.job_id)}catch(e){setMsg(e.message);setBusy(false)}}
 const isPii=module.id==='pii'
 return <><button className="back" onClick={back}>← Modules</button><PageTitle title={module.name} sub={module.desc}/><div className="workspace"><Panel title={isPii?'PII classification & protection':'Source file'} sub={isPii?'Classification is GenAI-assisted and based on the existing engine’s column metadata workflow.':'Upload a source asset and run the real Python conversion engine.'}>{module.id==='uiux'?<div className="prompt-box"><label>Dashboard brief</label><textarea value={prompt} onChange={e=>setPrompt(e.target.value)} /><button className="primary full" onClick={submit} disabled={busy}>{busy?'Generating…':'Generate Power BI concept'}</button></div>:<div className="drop"><input type="file" accept={module.accept} onChange={e=>setFile(e.target.files[0])}/><div className="drop-icon">⇧</div><strong>{file?file.name:'Drop a file here or browse'}</strong><small>{file?`${(file.size/1024/1024).toFixed(2)} MB`:module.accept}</small></div>}{isPii?<><div className="actions"><button className="primary" onClick={scan} disabled={busy}>Run GenAI PII classification</button></div>{piiCols.length>0&&<><h3 className="mini-title">Detected columns</h3><div className="chips">{piiCols.map(c=><button key={c} className={selected.includes(c)?'chip selected':'chip'} onClick={()=>setSelected(x=>x.includes(c)?x.filter(y=>y!==c):[...x,c])}>{c}</button>)}</div><div className="key-row"><input value={key} onChange={e=>setKey(e.target.value)} placeholder="Optional Fernet key — leave blank to generate"/><button className="secondary" onClick={mask} disabled={busy}>Protect selected values</button></div></>}</>:module.id!=='uiux'&&<button className="primary full" onClick={submit} disabled={busy}>{busy?'Processing…':'Run '+module.name}</button>}</Panel><Panel title="Execution"  sub="Live job status from FastAPI." ><div className="exec"><div><span>Engine</span><strong>Python · {module.id.toUpperCase()}</strong></div><div><span>Status</span><strong className={busy?'running':''}>{job?.status||'Ready'}</strong></div>{msg&&<div className="message">{msg}</div>}{job?.status==='completed'&&<a className="download" href={'/api/jobs/'+job.id+'/download'}>Download generated output →</a>}</div></Panel></div></>
}
createRoot(document.getElementById('root')).render(<App/>)
