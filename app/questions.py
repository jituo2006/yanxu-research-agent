"""Question-level answers bound to observed excerpts, never source counts.

An excerpt match proves provenance, not semantic support. Support judgments keep
model/human origin and are explicitly subject to review.
"""
import hashlib
import json
import re
from copy import deepcopy
from . import store
from .fact_state import assert_claims, verification

LABELS={'pending':'待处理','partial':'部分回答','supported':'有证据回答 · 待复核','conflict':'证据冲突','unverifiable':'无法验证'}


def text(value,label,limit=2000,required=True):
    if not isinstance(value,str) or len(value)>limit or required and not value.strip(): raise ValueError(label+'需为有效文本')
    return value.strip()


def create(question,criteria='给出对应问题的回答，并绑定原文证据、说明反证及缺口。'):
    question=text(question,'研究问题',1000);criteria=text(criteria,'完成条件',1500)
    return {'id':'q-'+hashlib.sha256(question.encode()).hexdigest()[:12],'question':question,'completion_criteria':criteria,
        'status':'pending','answer':'','bindings':[],'counter_evidence':'','gaps':[],'next_action':'','assessment_origin':'none'}


def inventory(run):
    return deepcopy(run.get('research_questions') or [create(run['request'].get('question','当前研究还有哪些证据缺口？'))])


def plan(run_id,items):
    if not isinstance(items,list) or not 1<=len(items)<=20: raise ValueError('每次提出1—20项研究问题')
    prepared=[create(i['question'],i.get('completion_criteria','给出问题答案并绑定支持与反方原文，保留缺口。')) if isinstance(i,dict) and 'question' in i else create(i) for i in items]
    def change(run):
        current=inventory(run);known={i['id'] for i in current}
        for item in prepared:
            if item['id'] not in known: current.append(item);known.add(item['id'])
        if len(current)>50: raise ValueError('研究最多保存50项问题，请收敛任务范围')
        run['research_questions']=current
    saved=store.update_run(run_id,change)
    return snapshot(saved)


def catalog(run):
    from .deep_research import reference_catalog
    refs=reference_catalog(run)
    # Original evidence is also addressable at its exact document/row locator.
    for source in run.get('evidence',[]):
        day=str(source.get('announced_date') or '').replace('-','')[:8]
        if day and day>run['request']['as_of'].replace('-',''): continue
        refs[source['id']]={**source,'text':source.get('quote',''),'url':source.get('source_url'),
            'published_at':source.get('announced_date'),'read_status':'original_record'}
    for f in run.get('facts',[]):
        if f['id'] not in refs: continue
        refs[f['id']]['text']='\n'.join(s.get('quote','') for s in run.get('evidence',[]) if s['id'] in f.get('evidence_ids',[]))
        refs[f['id']]['locator']=f.get('label',f['id'])+' '+str(f.get('year'))+'年'
    cutoff=run['request']['as_of'].replace('-','')
    return {k:s for k,s in refs.items() if not s.get('published_at') or str(s['published_at']).replace('-','')[:8]<=cutoff}


def normal(value): return re.sub(r'\s+','',value)


def assess(run,item,origin='model'):
    current=next((q for q in inventory(run) if q['id']==item.get('question_id',item.get('id'))),None)
    if not current: raise ValueError('问题ID不存在，请先建立研究问题')
    status=item.get('status','partial')
    if status not in LABELS: raise ValueError('问题状态无效')
    answer=text(item.get('answer',''),'答案',8000,False)
    counter=text(item.get('counter_evidence',''),'反方说明',3000,False)
    gaps=item.get('gaps',[])
    if not isinstance(gaps,list) or len(gaps)>20: raise ValueError('缺口需为最多20项文本列表')
    gaps=[text(g,'证据缺口',1000) for g in gaps]
    bindings=item.get('bindings',[])
    if not isinstance(bindings,list) or len(bindings)>20: raise ValueError('证据绑定最多20项')
    refs=catalog(run);checked=[];usable=0;has_conflict=False
    for binding in bindings:
        if not isinstance(binding,dict): raise ValueError('证据绑定需为对象')
        sid=binding.get('source_id');source=refs.get(sid)
        if not source: raise ValueError('引用来源不存在或晚于截止日')
        quote=text(binding.get('quote'),'原文摘录',2500)
        if len(normal(quote))<4 or normal(quote) not in normal(source.get('text','')):
            raise ValueError('引用摘录未在实际取得的原文中匹配')
        relation=binding.get('relation','support')
        if relation not in ('support','counter'): raise ValueError('关系必须为support或counter')
        reason=text(binding.get('reason'),'证据与问题的关系',1500)
        digest=hashlib.sha256(source.get('text','').encode()).hexdigest()
        if binding.get('source_hash') and binding['source_hash']!=digest: gaps.append('所用来源内容已变化，需重新确认摘录语境')
        state=source.get('read_status')
        day=str(source.get('published_at') or '').replace('-','')[:8]
        qualifying=bool(day) and state not in ('search_snippet','snippet_only','windows_ocr') and source.get('kind') not in ('valuation','calculation')
        if not day: gaps.append('引用来源日期未知，不能证明截止日内已知')
        if state in ('search_snippet','snippet_only'): gaps.append('搜索摘要不构成问题完成所需原文')
        if state=='windows_ocr': gaps.append('OCR来源需要人工核对原图')
        associated=[f for f in run.get('facts',[]) if f['id']==sid or sid in f.get('evidence_ids',[])]
        if any(verification(f,run.get('evidence',[]))['state']=='conflict' for f in associated): has_conflict=True
        if any(verification(f,run.get('evidence',[]))['state'] in ('conflict','ocr_pending','missing','unverified') for f in associated): qualifying=False
        if qualifying and relation=='support': usable+=1
        checked.append({'source_id':sid,'quote':quote,'relation':relation,'reason':reason,'source_hash':digest,
            'title':source.get('title') or source.get('locator') or sid,'url':source.get('url'),
            'page':source.get('page'),'locator':source.get('locator'),'published_at':source.get('published_at'),
            'read_status':state,'qualifying':qualifying})
    if status=='supported' and not counter: gaps.append('尚未记录反方或替代解释')
    if status=='supported' and (not answer or not usable or gaps):
        status='partial'
        if not usable: gaps.append('尚无具备日期与原文的支持证据')
        if not answer: gaps.append('尚未给出问题答案')
    if has_conflict: status='conflict';gaps.append('关联财务事实存在来源冲突')
    assert_claims(answer,run,[b['source_id'] for b in checked])
    return {**current,'status':status,'answer':answer,'bindings':checked,'counter_evidence':counter,
        'gaps':list(dict.fromkeys(gaps)),'next_action':text(item.get('next_action',''),'下一步',1500,False),'assessment_origin':origin,
        'semantic_validation':'excerpt_match_only; support_judgment_requires_review'}


def validate_updates(run,updates,origin='model'):
    if not isinstance(updates,list) or len(updates)>50: raise ValueError('问题答案需为最多50项列表')
    if any(not isinstance(i,dict) for i in updates): raise ValueError('问题答案需为对象')
    ids=[i.get('question_id',i.get('id')) for i in updates]
    if len(ids)!=len(set(ids)): raise ValueError('同一批次问题不能重复更新')
    return [assess(run,i,origin) for i in updates]


def apply(run,updates):
    current=inventory(run);lookup={q['id']:q for q in current}
    for answer in updates:
        old=lookup[answer['id']]
        compare=lambda q:{k:v for k,v in q.items() if k not in ('history','updated_at','label')}
        if compare(answer)==compare(old): continue
        history=old.get('history',[])+[{k:v for k,v in old.items() if k!='history'}]
        old.update(answer,history=history,updated_at=store.now())
    run['research_questions']=current


def update(run_id,updates,origin='model'):
    def change(run):apply(run,validate_updates(run,updates,origin))
    return snapshot(store.update_run(run_id,change))


def snapshot(run):
    items=[]
    for q in inventory(run):
        try:
            item=assess(run,q,q.get('assessment_origin','none')) if q.get('bindings') else q
        except ValueError as e:
            item={**q,'status':'partial','gaps':list(dict.fromkeys(q.get('gaps',[])+['来源需重新核对：'+str(e)]))}
        if item.get('status')=='supported' and not item.get('bindings'):item={**item,'status':'partial','gaps':['缺少原文绑定']}
        items.append({**item,'label':LABELS[item['status']]})
    counts={s:sum(q['status']==s for q in items) for s in LABELS}
    return {'items':items,'total':len(items),'counts':counts,'complete':bool(items) and counts['supported']==len(items),
        'note':'问题状态由答案及逐条原文绑定约束；摘录匹配不代表因果/投资判断已经独立验证。'}


def bounded_catalog(run,budget=65000):
    result=[]
    for source in catalog(run).values():
        if budget<=0: break
        value=dict(source);value['text']=source.get('text','')[:min(8000,budget)]
        budget-=len(value['text']);result.append(value)
    return result
