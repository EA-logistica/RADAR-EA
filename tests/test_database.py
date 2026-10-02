from datetime import date
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from fastapi.testclient import TestClient
from radar.normalize import normalize_ma
from radar.etl import load
from radar.models import Operation, Revision, Alert
from radar.api import app
from radar.db import session_dependency

def row(raw,artifact): return {**normalize_ma(raw),'artifact_id':artifact['id']}

def test_idempotent_and_revision(db,raw,artifact):
    r=row(raw,artifact)
    assert load(db,[artifact],[r])['inserted']==1
    assert load(db,[artifact],[r])['unchanged']==1
    changed=row({**raw,'FOB_DOLPOL':'28000','FMOD':'20260902'},artifact)
    assert load(db,[artifact],[changed])['updated']==1
    assert db.scalar(select(func.count()).select_from(Operation))==1
    assert db.scalar(select(func.count()).select_from(Revision))==2
    assert load(db,[artifact],[r])['older_ignored']==1

def test_web_does_not_replace_bulk(db,raw,artifact):
    r=row(raw,artifact);load(db,[artifact],[r])
    web=row({**raw,'DNOMBRE':''},artifact);web['source_priority']=10
    assert load(db,[artifact],[web])['older_ignored']==1
    assert db.scalar(select(Operation)).importer=='EMPRESA PLASTICA SAC'

def test_web_name_enrichment_by_exact_ruc(db,raw,artifact):
    load(db,[artifact],[row(raw,artifact)])
    web=row({**raw,'NUME_CORRE':'123457','DNOMBRE':''},artifact);web['source_priority']=10
    load(db,[artifact],[web])
    op=db.scalar(select(Operation).where(Operation.declaration=='123457'))
    assert op.importer=='EMPRESA PLASTICA SAC'
    assert op.raw['ma']['DNOMBRE']==''
    assert op.raw['_enrichment']['exact_ruc']=='20100367395'

def test_locked_classification_survives(db,raw,artifact):
    r=row(raw,artifact);load(db,[artifact],[r]);op=db.scalar(select(Operation));op.material='Otros';op.classification_locked=True;db.commit()
    load(db,[artifact],[row({**raw,'FOB_DOLPOL':'28000'},artifact)])
    assert db.scalar(select(Operation)).material=='Otros'

def test_alert_baseline_and_dedup(db,raw,artifact):
    load(db,[artifact],[row(raw,artifact)],baseline=None)
    assert db.scalar(select(func.count()).select_from(Alert))==0
    updated=row({**raw,'NUME_CORRE':'123457','FECH_INGSI':'20260910','PESO_NETO':'10000','FOB_DOLPOL':'30000'},artifact)
    load(db,[artifact],[updated],baseline=date(2026,9,1))
    count=db.scalar(select(func.count()).select_from(Alert));assert count==3
    load(db,[artifact],[updated],baseline=date(2026,9,1))
    assert db.scalar(select(func.count()).select_from(Alert))==count

def test_api_search_export_profile(db,raw,artifact):
    load(db,[artifact],[row(raw,artifact)])
    app.dependency_overrides[session_dependency]=lambda:db
    try:
        with TestClient(app) as c:
            assert c.get('/api/operations?q=HDPE+soplado+MI+0.35').json()['total']==1
            assert c.get('/api/operations?q=HDPE+soplado+MI+0.3').json()['total']==0
            assert c.get('/api/operations?q=PP').json()['total']==0
            assert c.get('/api/operations?start=2026-09-02').json()['total']==0
            assert c.get('/api/operations?start=2026-09-02&end=2026-09-01').status_code==422
            assert c.get('/api/operations?page=0').status_code==422
            assert c.get('/api/company/20100367395').json()['summary']['operations']==1
            assert c.get('/api/material/HDPE').json()['summary']['series']==1
            assert c.get('/api/compare?rucs=20100367395,20100024862').status_code==200
            assert c.get('/api/export?format=csv').content.startswith(b'\xef\xbb\xbf')
            assert c.get('/api/export?format=xlsx').content.startswith(b'PK')
            op=db.scalar(select(Operation))
            assert c.get(f'/api/operations/{op.id}').json()['raw']['ma']['DESC_COMER']==raw['DESC_COMER']
            assert c.post(f'/api/operations/{op.id}/review',json={'material':'Otros','note':'Revisión con ficha técnica'}).status_code==200
            assert c.get(f'/api/operations/{op.id}').json()['classification_locked'] is True
    finally: app.dependency_overrides.clear()

def test_export_formula_escape():
    from radar.api import safe_cell
    assert safe_cell(' =HYPERLINK("x")').startswith("'")
    assert safe_cell('@SUM(1)')=="'@SUM(1)"
    assert safe_cell(12)==12
