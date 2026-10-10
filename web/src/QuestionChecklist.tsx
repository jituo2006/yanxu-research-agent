import {useEffect,useState} from 'react';
import {api,post} from './api';
export default function QuestionChecklist({run,onDiscuss,onUpdated}:any){
 const [view,setView]=useState<any>(run.question_coverage),[error,setError]=useState(''),[question,setQuestion]=useState(''),[busy,setBusy]=useState(false),[editing,setEditing]=useState('');
 const [sources,setSources]=useState<any[]>([]),[answer,setAnswer]=useState(''),[quote,setQuote]=useState(''),[source,setSource]=useState(''),[reason,setReason]=useState(''),[gap,setGap]=useState(''),[counter,setCounter]=useState('');
 useEffect(()=>{setView(run.question_coverage);api('/runs/'+run.id+'/questions').then(setView).catch(e=>setError(e.message));api('/runs/'+run.id+'/question-sources').then(setSources).catch(e=>setError(e.message))},[run.id,run.updated_at]);
 async function add(e:any){e.preventDefault();setBusy(true);setError('');try{const v=await post('/runs/'+run.id+'/questions',{questions:[question]});setView(v);setQuestion('');await onUpdated(run.id)}catch(e:any){setError(e.message)}finally{setBusy(false)}}
 function edit(q:any){setEditing(q.id);setAnswer(q.answer||'');setCounter(q.counter_evidence||'');setGap((q.gaps||[]).join('\n'));setSource('');setQuote('');setReason('')}
 async function save(e:any){e.preventDefault();setBusy(true);setError('');try{const v=await post('/runs/'+run.id+'/question-answers',{answers:[{question_id:editing,answer,status:source?'supported':'partial',bindings:source?[{source_id:source,quote,relation:'support',reason}]:[],gaps:gap.split('\n').filter(s=>s.trim()),counter_evidence:counter,next_action:''}]});setView(v);setEditing('');await onUpdated(run.id)}catch(e:any){setError(e.message)}finally{setBusy(false)}}
 const selected=sources.find(s=>s.id===source),locked=busy||['queued','running'].includes(run.state);
 return <div className="content-page"><div className="section-heading"><div><h1>问题与证据</h1><p>{view?.note}</p></div><span className="badge">{view?.counts?.supported||0} / {view?.total||0} 项有证据回答</span></div>
 {error&&<p className="form-error" role="alert">{error}</p>}
 <form className="panel pad" onSubmit={add}><label>增加具体研究问题<input required maxLength={1000} value={question} onChange={e=>setQuestion(e.target.value)} placeholder="例如：有没有可核对的付费合同？"/></label><button className="secondary" disabled={locked||!question.trim()}>加入清单</button></form>
 {(view?.items||[]).map((q:any)=><section className="panel pad" key={q.id}><div className="panel-heading"><h2>{q.question}</h2><span className="badge">{q.label}</span></div><p>完成条件：{q.completion_criteria}</p><p>{q.answer||'尚未回答'}</p>
 {q.bindings?.map((b:any,i:number)=><div key={i}><blockquote>{b.quote}</blockquote><p>{b.relation==='counter'?'反方':'支持'}：{b.reason} · {b.url?<a href={b.url} target="_blank" rel="noreferrer">{b.title}</a>:b.title}{b.locator?' · '+b.locator:''}</p></div>)}
 <p>反方：{q.counter_evidence||'待补充'}</p>{q.gaps?.length>0&&<ul>{q.gaps.map((g:string,i:number)=><li key={i}>{g}</li>)}</ul>}
 <p>评估来源：{q.assessment_origin==='human'?'人工记录':q.assessment_origin==='model'?'模型判断，待复核':'尚未评估'}{q.next_action?' · 下一步：'+q.next_action:''}</p>
 <div className="button-row"><button className="text-link" onClick={()=>onDiscuss(`请继续查证问题 ${q.id}：“${q.question}”。完成条件：${q.completion_criteria}。读取实际原文，通过 update_research_question 保存逐条支持、反证和缺口；没有证据不要标成完成。`)}>继续查证</button><button className="text-link" disabled={locked} onClick={()=>edit(q)}>人工记录证据</button></div>
 {editing===q.id&&<form onSubmit={save}><label>问题答案<textarea required value={answer} onChange={e=>setAnswer(e.target.value)}/></label><label>实际取得的来源<select value={source} onChange={e=>{setSource(e.target.value);setQuote('')}}><option value="">仅记录部分答案/缺口</option>{sources.map(s=><option key={s.id} value={s.id}>{s.title||s.id}</option>)}</select></label>{selected&&<details open><summary>已读取的来源文字（可能截断）</summary><pre style={{whiteSpace:'pre-wrap',maxHeight:240,overflow:'auto'}}>{selected.text||'该来源尚无可绑定原文'}</pre></details>}
 {source&&<><label>连续原文摘录<textarea required value={quote} onChange={e=>setQuote(e.target.value)}/></label><label>该证据如何回答问题<input required value={reason} onChange={e=>setReason(e.target.value)}/></label></>}
 <label>反方/替代解释<textarea value={counter} onChange={e=>setCounter(e.target.value)}/></label><label>仍缺什么（每行一项）<textarea value={gap} onChange={e=>setGap(e.target.value)}/></label><p>有缺口、仅摘要或日期未知时会保存为部分回答。人工记录不自动改写报告。</p><button className="primary" disabled={locked}>保存记录</button><button type="button" className="secondary" onClick={()=>setEditing('')}>取消</button></form>}
 {q.history?.length>0&&<details><summary>查看 {q.history.length} 次历史记录</summary>{q.history.map((v:any,i:number)=><div key={i}><strong>{v.status}</strong><p>{v.answer||'尚未回答'}</p></div>)}</details>}
 </section>)}
 </div>
}
