"""Process one supplied task in an isolated workspace; no model by default."""
import argparse
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
p=argparse.ArgumentParser()
p.add_argument('--workspace',required=True);p.add_argument('--policy');p.add_argument('--ticker',required=True);p.add_argument('--year',type=int,required=True);p.add_argument('--as-of',required=True)
p.add_argument('--question',default='核对材料中收入、利润和现金流变化，说明证据与缺口。');p.add_argument('--material',action='append',default=[]);p.add_argument('--pdf');p.add_argument('--announced-date');p.add_argument('--model',action='store_true')
a=p.parse_args()
os.environ['RESEARCH_DATA_DIR']=str(Path(a.workspace).resolve());os.environ['RESEARCH_COMPETITION_MODE']='1';os.environ.pop('RESEARCH_COMPETITION_POLICY_JSON',None)
if a.policy:os.environ['RESEARCH_COMPETITION_POLICY']=str(Path(a.policy).resolve())
from app import store,documents,research,competition
from app.schemas import RunRequest
# User-selected input paths are an explicit import boundary, never agent-readable paths.
ids=[]
for filename in a.material:
 path=Path(filename);ids.append(competition.register_material(path.read_bytes(),path.name,a.ticker,a.year,a.announced_date)['id'])
doc=None
if a.pdf:
 path=Path(a.pdf);doc=documents.register_pdf(path.read_bytes(),a.ticker,a.year,path.name,a.announced_date)['id']
request=RunRequest(ticker=a.ticker,year=a.year,as_of=a.as_of,question=a.question,mode='live',data_source='documents',use_model=a.model,document_id=doc,material_ids=ids)
run=store.create_run(request.model_dump(mode='json'));research.execute(run['id']);run=store.get_run(run['id'])
output=store.DATA/('submission-'+run['id']+'.zip');output.write_bytes(competition.submission_bundle(run))
print(run['id'],run['state'],output)
if run['state'] in ('failed','blocked') or a.model and run['model']['status']!='completed':sys.exit(1)
