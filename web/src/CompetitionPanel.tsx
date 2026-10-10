import {useEffect,useState} from 'react';
import {api,post} from './api';
export default function CompetitionPanel({run,onCreated}:any){
 const [policy,setPolicy]=useState<any>(null),[materials,setMaterials]=useState<any[]>([]),[docs,setDocs]=useState<any[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const [form,setForm]=useState<any>({ticker:'000333.SZ',year:2025,as_of:new Date().toLocaleDateString('en-CA'),question:'核对指定材料中的收入、利润与现金流，说明证据和缺口。',document_id:'',material_ids:[],use_model:true});
 async function refresh(){const [p,m,d]=await Promise.all([api('/competition'),api('/competition/materials'),api('/documents')]);setPolicy(p);setMaterials(m);setDocs(d)}
 useEffect(()=>{refresh().catch(e=>setError(e.message))},[]);
 async function upload(file:File){setBusy(true);setError('');try{const data=new FormData();data.append('file',file);data.append('ticker',form.ticker);data.append('year',String(form.year));await api('/competition/materials',{method:'POST',body:data});await refresh()}catch(e:any){setError(e.message)}finally{setBusy(false)}}
 async function create(e:any){e.preventDefault();setBusy(true);setError('');try{const r=await post('/runs',{...form,year:Number(form.year),document_id:form.document_id||null,mode:'live',data_source:'documents'});await onCreated(r.id)}catch(e:any){setError(e.message)}finally{setBusy(false)}}
 return <div className="content-page"><div className="section-heading"><div><h1>比赛工作区</h1><p>固定材料、访问限制与执行审计。状态以当前启动配置为准。</p></div></div>
 {error&&<p className="form-error" role="alert">{error}</p>}
 <section className="panel pad"><h2>{policy?.enabled?'受控模式已启用':'当前为普通模式'}</h2><p>{policy?.note}</p><p>数据目录：{policy?.data_directory}</p><p>模型许可：{policy?.model_origins?.join('、')||'无'}</p><p>资料网络许可：{policy?.retrieval_origins?.join('、')||'无'}</p>{!policy?.enabled&&<p>使用 scripts/start-competition.ps1 启动独立比赛工作区；普通模式下不接受结构化比赛材料导入。</p>}</section>
 {policy?.enabled&&<form className="panel pad" onSubmit={create}><h2>指定材料任务</h2><div className="valuation-fields">
 <label>证券代码<input required value={form.ticker} onChange={e=>setForm({...form,ticker:e.target.value,document_id:'',material_ids:[]})}/></label>
 <label>年度<input type="number" min="2000" max="2100" value={form.year} onChange={e=>setForm({...form,year:e.target.value,document_id:'',material_ids:[]})}/></label>
 <label>研究截止日<input type="date" required value={form.as_of} onChange={e=>setForm({...form,as_of:e.target.value})}/></label>
 <label>PDF材料<select value={form.document_id} onChange={e=>setForm({...form,document_id:e.target.value})}><option value="">不绑定PDF</option>{docs.filter(d=>d.ticker===form.ticker&&Number(d.year)===Number(form.year)).map(d=><option key={d.id} value={d.id}>{d.title}</option>)}</select></label></div>
 <p>PDF通过资料库上传。JSON/CSV字段格式见 docs/competition/mode.md；缺日期或口径的数据不会自动成为核验事实。</p>
 <label>导入JSON/CSV<input type="file" accept=".json,.csv" disabled={busy} onChange={e=>{if(e.target.files?.[0])upload(e.target.files[0]);e.target.value=''}}/></label>
 <fieldset><legend>参与本次研究的结构化材料</legend>{materials.filter(m=>m.ticker===form.ticker&&Number(m.year)===Number(form.year)).map(m=><label key={m.id}><input type="checkbox" checked={form.material_ids.includes(m.id)} onChange={e=>setForm({...form,material_ids:e.target.checked?[...form.material_ids,m.id]:form.material_ids.filter((id:string)=>id!==m.id)})}/>{m.filename} · {m.row_count}行</label>)}</fieldset>
 <label>研究问题<textarea required value={form.question} onChange={e=>setForm({...form,question:e.target.value})}/></label>
 <label><input type="checkbox" checked={form.use_model} onChange={e=>setForm({...form,use_model:e.target.checked})}/>使用真实模型生成研究（需配置并许可模型接口）</label>
 <button className="primary" disabled={busy||(!form.document_id&&!form.material_ids.length)}>{busy?'正在处理…':'建立指定材料研究'}</button></form>}
 {run&&<section className="panel pad"><h2>当前研究提交包</h2><p>包含报告、材料、计算、工作区审计、环境与文件哈希；模型重新运行不保证逐字一致。</p><a className="text-link" href={'/api/runs/'+run.id+'/submission'}>下载提交ZIP</a></section>}
 </div>
}
