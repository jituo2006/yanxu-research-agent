import copy
import json
import pytest
from fastapi.testclient import TestClient
from app import store, main, agent, deep_research, valuation
from app.fact_state import verification, claims, assert_claims


def fact(status='api_only',**extra):
    return {'id':'revenue-2025','metric':'revenue','label':'营业收入','year':2025,'value':'100','original_unit':'元',
        'evidence_ids':['api'],'status':status,'announced_date':'2026-03-31',**extra}


def run(f=None):
    return {'facts':[f or fact()],'evidence':[{'id':'api','kind':'api','quote':'revenue:100','locator':'接口响应'}],
        'request':{'year':2025,'as_of':'2026-09-28'},'state':'completed_with_gaps'}

@pytest.mark.parametrize('status,state',[('api_only','api_single'),('document_only','document_single'),('verified','legacy_match'),('conflict','conflict'),('missing','missing')])
def test_legacy_states_are_conservative(status,state):
    f=fact(status,value=None if status=='missing' else '100')
    assert verification(f)['state']==state


def test_cross_source_requires_actual_match_record():
    f=fact('verified',evidence_ids=['api','pdf']);e=[{'id':'api','kind':'api'},{'id':'pdf','kind':'document'}]
    assert verification(f,e)['state']=='legacy_match'
    f['cross_check_value']='100.2'
    assert verification(f,e)['state']=='cross_source_match'
    assert verification(f,e)['source_independence']=='not_assessed'
    f['cross_check_value']='101'
    assert verification(f,e)['state']=='conflict'


def test_ocr_is_not_formal_numeric_basis():
    f=fact('document_only',extraction='windows_ocr')
    assert verification(f)['state']=='ocr_pending'
    with pytest.raises(ValueError,match='OCR'):valuation.calculate(run(f),'ps',{'growth_pct':'1','multiple':'2'})

@pytest.mark.parametrize('text',['营业收入已核验。','2025年营业收入已通过双源核验。','这些财务数据已验证。'])
def test_single_source_cannot_be_upgraded_by_prose(text):
    assert claims(text,run())
    with pytest.raises(ValueError):assert_claims(text,run())

@pytest.mark.parametrize('text',['营业收入未双源核验。','营业收入尚未经过双源核验。','营业收入为接口单源。','不能称营业收入已核验。'])
def test_negative_or_state_disclosure_is_allowed(text):
    assert not claims(text,run())


def test_past_cutoff_not_eligible():
    assert not verification(fact(announced_date='2026-10-01'),as_of='2026-09-28')['usable_for_calculation']


def test_status_view_does_not_mutate_stored_history(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path)
    saved=store.create_run({'ticker':'600001.SH','year':2025,'question':'研究财务变化','as_of':'2026-09-28','mode':'live'})
    saved.update(facts=[fact()],evidence=run()['evidence']);store.save_run(saved)
    original=copy.deepcopy(store.get_run(saved['id']))
    with TestClient(main.app) as client:
        shown=client.get('/api/runs/'+saved['id']).json()
        assert shown['facts'][0]['verification']['state']=='api_single'
    assert store.get_run(saved['id'])==original


def test_report_cannot_overstate_even_with_valid_citation():
    r=run();r.update(calculations=[],valuation_history=[],research_sources=[])
    draft={'summary':'营业收入已核验','title':'研究','stance':'待观察','theses':[],'sections':[]}
    with pytest.raises(ValueError,match='状态'):deep_research.validate_memo(draft,r)


def test_attaching_source_does_not_upgrade_fact():
    r=run();r['research_sources']=[{'id':'pdf-read','kind':'pdf','text':'营业收入100'}]
    assert verification(r['facts'][0],r['evidence'])['state']=='api_single'
