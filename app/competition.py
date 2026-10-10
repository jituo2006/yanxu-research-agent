"""Startup-frozen application policy and credential-free competition audit.

This restricts application data reads/network calls, not Python or the host OS.
"""
import csv
import hashlib
import io
import json
import os
import re
import sqlite3
import time
import uuid
from contextvars import ContextVar
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit
from . import store
from .config import ROOT, FIXTURES, VERSION

_context = ContextVar('competition_context', default={})
_secret = re.compile(r'key|token|secret|authorization|password', re.I)

class PolicyError(ValueError):
    pass


def load_policy():
    enabled = os.environ.get('RESEARCH_COMPETITION_MODE', '').lower() in ('1','true','yes')
    if not enabled:
        return {'enabled':False,'model_origins':[],'retrieval_origins':[]}
    if not os.environ.get('RESEARCH_DATA_DIR'):
        raise PolicyError('比赛模式必须通过RESEARCH_DATA_DIR指定独立工作区')
    if store.DATA.resolve()==(ROOT/'var').resolve():
        raise PolicyError('比赛工作区不能使用普通模式默认var目录')
    path = Path(os.environ.get('RESEARCH_COMPETITION_POLICY', store.DATA/'competition-policy.json'))
    frozen=os.environ.get('RESEARCH_COMPETITION_POLICY_JSON')
    policy = json.loads(frozen) if frozen else json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
    if not isinstance(policy,dict) or set(policy)-{'enabled','model_origins','retrieval_origins'}:
        raise PolicyError('比赛策略包含未知字段')
    result = {'enabled':True}
    for key in ('model_origins','retrieval_origins'):
        values = policy.get(key, [])
        if not isinstance(values,list) or len(values)>100: raise PolicyError('比赛网络许可必须为来源列表')
        result[key] = sorted(set(origin(v) for v in values))
    return result


def origin(url):
    p=urlsplit(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password:
        raise PolicyError('网络许可需要明确HTTP/HTTPS来源，不允许凭据或通配符')
    host=p.hostname.lower().rstrip('.')
    if '*' in host: raise PolicyError('网络许可不支持通配符')
    try: port=p.port or (443 if p.scheme=='https' else 80)
    except ValueError: raise PolicyError('网络端口无效') from None
    return f'{p.scheme}://{host}:{port}'

# Loaded once, before worker/API startup. A running task cannot rewrite its policy.
POLICY=load_policy()
if POLICY["enabled"]:
    os.environ["RESEARCH_COMPETITION_POLICY_JSON"]=json.dumps(POLICY)


def clean(value):
    if isinstance(value,dict): return {str(k):('[REDACTED]' if _secret.search(str(k)) and str(k) not in ('max_tokens','max_completion_tokens') else clean(v)) for k,v in value.items()}
    if isinstance(value,list): return [clean(v) for v in value]
    if isinstance(value,Path): return str(value)
    if isinstance(value,str):
        value=re.sub(r'(?i)(bearer\s+)[\w.-]+',r'\1[REDACTED]',value)
        value=re.sub(r'\bsk-[A-Za-z0-9_-]{8,}', '[REDACTED]',value)
        return value
    return value


def audit(kind, **fields):
    if not POLICY['enabled']: return
    store.DATA.mkdir(parents=True,exist_ok=True)
    value=clean({'time':store.now(),'kind':kind,**_context.get(),**fields})
    with sqlite3.connect(store.DATA/'competition-audit.sqlite3',timeout=15) as c:
        c.execute('CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT NOT NULL)')
        c.execute('INSERT INTO audit(payload) VALUES (?)',(json.dumps(value,ensure_ascii=False,default=str),))


@contextmanager
def scope(**fields):
    token=_context.set({**_context.get(),**fields})
    try: yield
    finally: _context.reset(token)


def traced(kind, identity=None):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args,**kwargs):
            fields={identity:str(args[0])} if identity and args else {}
            started=time.monotonic()
            with scope(**fields):
                audit(kind+'_start',arguments=kwargs)
                try:
                    result=fn(*args,**kwargs)
                    audit(kind+'_result',elapsed_ms=int((time.monotonic()-started)*1000),result=result)
                    return result
                except Exception as e:
                    audit(kind+'_error',error_type=type(e).__name__,message=str(e)[:1000])
                    raise
        return wrapped
    return decorate


def check_network(url, purpose='retrieval'):
    if not POLICY['enabled']: return
    if purpose not in ('model','retrieval'): raise PolicyError('未知网络用途')
    target=origin(url)
    allowed=target in POLICY[purpose+'_origins']
    audit('network_access',purpose=purpose,origin=target,path=urlsplit(url).path,status='allowed' if allowed else 'blocked')
    if not allowed: raise PolicyError('比赛模式禁止该'+('模型' if purpose=='model' else '资料')+'网络来源：'+target)


def check_file(path):
    resolved=Path(path).resolve()
    if POLICY['enabled']:
        roots=[store.DATA.resolve(),FIXTURES.resolve()]
        # Runtime credential stores are not research materials even inside DATA.
        forbidden=resolved.name in ('connections.json','.env','competition-policy.json') or resolved.name.endswith('.sqlite3')
        allowed=not forbidden and any(resolved.is_relative_to(root) for root in roots)
        audit('file_access',path=str(resolved),status='allowed' if allowed else 'blocked')
        if not allowed: raise PolicyError('比赛模式仅允许读取工作区内研究材料')
    return resolved


def read_bytes(path):
    p=check_file(path);content=p.read_bytes()
    audit('file_read',path=str(p),sha256=hashlib.sha256(content).hexdigest(),bytes=len(content))
    return content


def read_json(path):
    return json.loads(read_bytes(path).decode('utf-8-sig'))


def status():
    return {**POLICY,'data_directory':str(store.DATA.resolve()),'scope':'application','version':VERSION,
        'note':'应用层访问控制；操作系统和比赛机器网络隔离需另行配置。'}


def register_material(content,filename,ticker,year,announced_date=None):
    if not POLICY['enabled']: raise PolicyError('请启动比赛模式后导入结构化材料')
    if len(content)>10*1024*1024: raise ValueError('结构化材料不得超过10MB')
    if not re.fullmatch(r'\d{6}\.(SZ|SH|BJ)',ticker): raise ValueError('证券代码无效')
    if not 2000<=year<=2100: raise ValueError('材料年度无效')
    suffix=Path(filename).suffix.lower()
    try:
        text=content.decode('utf-8-sig')
        if suffix=='.json':
            rows=json.loads(text)
            if isinstance(rows,dict): rows=rows.get('rows')
        elif suffix=='.csv': rows=list(csv.DictReader(io.StringIO(text)))
        else: raise ValueError('结构化材料支持JSON或CSV；PDF请用资料上传')
        if not isinstance(rows,list) or not 1<=len(rows)<=10000 or any(not isinstance(r,dict) for r in rows):
            raise ValueError('材料需为非空rows对象列表，最多10000行')
    except (UnicodeError,json.JSONDecodeError,csv.Error): raise ValueError('材料必须为有效UTF-8 JSON/CSV') from None
    identity=uuid.uuid4().hex[:16];folder=store.DATA/'competition-materials';folder.mkdir(parents=True,exist_ok=True)
    path=folder/(identity+suffix);path.write_bytes(content)
    item={'id':identity,'filename':Path(filename).name,'ticker':ticker,'year':year,'announced_date':announced_date,
        'path':str(path),'sha256':hashlib.sha256(content).hexdigest(),'row_count':len(rows),'created_at':store.now()}
    (folder/(identity+'.meta.json')).write_text(json.dumps(item,ensure_ascii=False),encoding='utf-8')
    audit('material_import',material=item)
    return {k:v for k,v in item.items() if k!='path'}


def materials():
    folder=store.DATA/'competition-materials'
    return [{k:v for k,v in read_json(p).items() if k!='path'} for p in sorted(folder.glob('*.meta.json'))]


def read_material(identity):
    if not re.fullmatch(r'[a-f0-9]{16}',identity): raise ValueError('材料ID无效')
    meta=read_json(store.DATA/'competition-materials'/(identity+'.meta.json'))
    content=read_bytes(meta['path'])
    if hashlib.sha256(content).hexdigest()!=meta['sha256']: raise ValueError('材料哈希已变化，需重新导入')
    text=content.decode('utf-8-sig')
    rows=json.loads(text) if Path(meta['path']).suffix=='.json' else list(csv.DictReader(io.StringIO(text)))
    if isinstance(rows,dict): rows=rows['rows']
    return meta,rows


def apply_materials(run):
    from decimal import Decimal
    from datetime import date
    from .finance import METRICS, number
    for identity in run['request'].get('material_ids',[]):
        meta,rows=read_material(identity)
        if meta['ticker']!=run['request']['ticker'] or meta['year']!=run['request']['year']:
            raise ValueError('结构化材料公司或年度不匹配')
        for n,row in enumerate(rows,1):
            metric=row.get('metric')
            if metric not in METRICS: continue
            year=int(row.get('year',0));value=number(row.get('value'));unit=row.get('unit')
            announced=row.get('announced_date') or meta.get('announced_date')
            if year not in (run['request']['year'],run['request']['year']-1): continue
            if not announced or date.fromisoformat(announced).isoformat()>run['request']['as_of']:
                run['gaps'].append({'code':f'material-date-{identity}-{n}','message':'结构化材料缺公告日或晚于截止日，该行未并入财务事实'});continue
            if value is None or unit not in ('元','千元','万元') or row.get('currency')!='CNY' or row.get('scope')!='consolidated' or row.get('period_type')!='annual':
                raise ValueError(f'材料第{n}行缺少有效数值、单位、币种或年度合并口径')
            value*=Decimal({'元':1,'千元':1000,'万元':10000}[unit]);eid=f'material-{identity}-row-{n}';fid=f'{metric}-{year}'
            run['evidence'].append({'id':eid,'kind':'material','title':meta['filename'],'material_id':identity,'sha256':meta['sha256'],
                'announced_date':announced,'retrieved_at':meta['created_at'],'locator':f'结构化材料第{n}行','quote':json.dumps(row,ensure_ascii=False)})
            old=next((f for f in run['facts'] if f['id']==fid),None)
            if old:
                old['evidence_ids'].append(eid)
                # Imported tables are not independent verification of a PDF/API.
                if number(old['value'])!=value: old['status']='conflict'
            else:
                run['facts'].append({'id':fid,'metric':metric,'label':METRICS[metric]['label'],'year':year,'value':str(value),
                    'original_value':str(row['value']),'original_unit':unit,'currency':'CNY','scope':'consolidated','period_type':'annual',
                    'announced_date':announced,'evidence_ids':[eid],'status':'document_only','missing_reason':None})


def submission_bundle(run):
    import zipfile
    import subprocess
    import importlib.metadata
    from .exporting import evidence_bundle
    audit('submission_export',run_id=run['id'])
    base=evidence_bundle(run,store.get_document,store.DATA/'runs'/run['id'])
    items={}
    with zipfile.ZipFile(io.BytesIO(base)) as z:
        items={name:z.read(name) for name in z.namelist()}
    for identity in run['request'].get('material_ids',[]):
        meta,_=read_material(identity);items['materials/'+identity+Path(meta['path']).suffix]=read_bytes(meta['path'])
        items['materials/'+identity+'.json']=json.dumps({k:v for k,v in meta.items() if k!='path'},ensure_ascii=False,indent=2).encode()
    if POLICY['enabled'] and (store.DATA/'competition-audit.sqlite3').exists():
        with sqlite3.connect(store.DATA/'competition-audit.sqlite3') as c:
            # Isolated workspace audit includes imports/network work for this workspace.
            events=[json.loads(r[0]) for r in c.execute('SELECT payload FROM audit ORDER BY seq')]
        items['competition/audit.json']=json.dumps(events,ensure_ascii=False,indent=2).encode()
    try: commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    except (OSError,subprocess.CalledProcessError): commit='unknown'
    versions={}
    for name in ('fastapi','httpx','pydantic','pdfplumber','pypdfium2'):
        try: versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: versions[name]='missing'
    items['competition/environment.json']=json.dumps({'app_version':VERSION,'commit':commit,'dependencies':versions,'policy':POLICY,
        'reproduction_modes':['deterministic_recompute','recorded_model_response','live_model_rerun'],
        'limitations':['模型重跑不保证逐字一致','审计为工作区范围，不包含连接密钥文件','应用层限制不是操作系统沙箱']},ensure_ascii=False,indent=2).encode()
    for relative in ('requirements-lock.txt','web/package-lock.json','app/agent.py','app/deep_research.py'):
        items['competition/reproducibility/'+relative]=(ROOT/relative).read_bytes()
    # Existing manifest is replaced because it must cover newly added files too.
    original_manifest=json.loads(items.pop('manifest.json',b'{}'))
    items['manifest.json']=json.dumps({**original_manifest,'files':[{'path':p,'sha256':hashlib.sha256(v).hexdigest(),'bytes':len(v)} for p,v in sorted(items.items())]},indent=2).encode()
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for p,v in items.items(): z.writestr(p,v)
    return output.getvalue()
