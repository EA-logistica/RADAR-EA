from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select,func
from radar.analytics import history, loaded_windows, timeline, metrics, bucket_start, bucket_end
from radar.api import app, Filters, conditions
from radar.db import session_dependency
from radar.models import Artifact, Run, Operation
from radar.normalize import normalize_ma
from radar.etl import load


def window(db,start,scope='plastics',committed=True,mb=True):
    end=start+timedelta(days=6)
    for kind in ['sunat_ma']+(['sunat_mb'] if mb else []):
        db.add(Artifact(id=uuid4().hex,source=kind,url='https://example.test/'+kind,path='fixture',period={'start':str(start),'end':str(end)},bytes=0))
    db.add(Run(id=str(uuid4()),kind='bulk',parameters={'scope':scope},status='failed',result={str(end):{'inserted':0}} if committed else {}))
    db.commit()


def add(db,raw,artifact,**overrides):
    values=normalize_ma({**raw,**overrides})
    load(db,[artifact],[{**values,'artifact_id':artifact['id']}],baseline=None)


def test_price_denominator_recurrence_and_first_observed(db,raw,artifact):
    for day in (date(2026,8,24),date(2026,8,31)): window(db,day)
    add(db,raw,artifact,NUME_CORRE='1',FECH_INGSI='20260825',FOB_DOLPOL='100',PESO_NETO='100',UNID_FIQTY='100')
    add(db,raw,artifact,NUME_CORRE='2',FOB_DOLPOL='100',PESO_NETO='100',UNID_FIQTY='100')
    add(db,raw,artifact,NUME_CORRE='2',NUME_SERIE='2',FOB_DOLPOL='900',PESO_NETO='300',UNID_FIQTY='300')
    add(db,raw,artifact,NUME_CORRE='3',LIBR_TRIBU='20100024862',DNOMBRE='Otra empresa',FOB_DOLPOL='50',PESO_NETO='',UNID_FIQTY='',UNID_FIDES='UND')
    result=history(db,Filters(start=date(2026,8,31),end=date(2026,9,6)),conditions)
    m=result['metrics']
    assert m['operations']==2 and m['series']==3
    assert m['usd_kg']==Decimal('2.5')  # 1,000 / 400; excludes unpaired USD 50.
    assert m['median_usd_kg']==2 and m['p25_usd_kg']==1.5 and m['p75_usd_kg']==2.5
    assert m['ticket_usd']==525 and m['tonnes_per_operation']==Decimal('.2')
    assert m['repeat_importers']==0  # Multiple series of one declaration aren't recurrent purchases.
    assert m['returning_importers']==1 and m['first_observed_importers']==1
    assert result['comparison']['eligible'] is True
    assert result['comparison']['deltas']['fob_usd']==950
    assert result['comparison']['deltas']['importers']==100
    assert m['top5_share_percent']==100


def test_gap_unknown_zero_and_partial_buckets(db,raw,artifact):
    window(db,date(2026,8,31));window(db,date(2026,9,14))
    add(db,raw,artifact)
    result=history(db,Filters(start=date(2026,8,31),end=date(2026,9,20)),conditions)
    a,gap,zero=result['timeline']
    assert a['status']=='backed'
    assert gap['status']=='missing' and gap['fob_usd'] is None and gap['operations'] is None
    assert zero['status']=='backed' and zero['fob_usd']==0 and zero['operations']==0
    assert zero['fob_change_percent'] is None  # Do not bridge a missing week.
    assert result['comparison']['eligible'] is False
    assert all(v is None for v in result['comparison']['deltas'].values())
    monthly=history(db,Filters(start=date(2026,8,31),end=date(2026,9,20)),conditions,grain='month')
    assert all(x['status']=='partial' for x in monthly['timeline'])


def test_window_requires_committed_pair_and_matching_scope(db):
    window(db,date(2026,8,3),committed=False)
    window(db,date(2026,8,10),mb=False)
    window(db,date(2026,8,17))
    window(db,date(2026,8,24),scope='all')
    assert len(loaded_windows(db,'plastics'))==2
    assert loaded_windows(db,'all')==[{'start':date(2026,8,24),'end':date(2026,8,30)}]


def test_default_comparison_uses_latest_base_not_query_day(db,raw,artifact):
    for n in range(8): window(db,date(2026,8,3)+timedelta(weeks=n))
    add(db,raw,artifact,FECH_INGSI='20260928')
    result=history(db,Filters(),conditions)
    assert result['meta']['available_end']==date(2026,9,28)
    assert result['current']['end']==date(2026,9,27)
    assert result['current']['start']==date(2026,8,31)
    assert result['previous']['start']==date(2026,8,3)
    assert result['comparison']['eligible']
    assert result['timeline'][-1]['status']=='partial'


def test_overlap_unequal_periods_and_zero_baseline(db):
    window(db,date(2026,8,24));window(db,date(2026,8,31))
    filters=Filters(start=date(2026,8,31),end=date(2026,9,6))
    result=history(db,filters,conditions,compare_start=date(2026,8,31),compare_end=date(2026,9,6))
    assert 'Los períodos se superponen' in result['comparison']['reasons']
    result=history(db,filters,conditions,compare_start=date(2026,8,24),compare_end=date(2026,8,25))
    assert 'Los períodos tienen distinta duración' in result['comparison']['reasons']
    result=history(db,filters,conditions)
    assert result['comparison']['eligible']
    assert all(v is None for v in result['comparison']['deltas'].values())
    with pytest.raises(HTTPException): history(db,filters,conditions,compare_start=date(2026,8,24))


def test_historical_api_filters_export_and_validation(db,raw,artifact):
    window(db,date(2026,8,31));add(db,raw,artifact)
    app.dependency_overrides[session_dependency]=lambda:db
    try:
        with TestClient(app) as c:
            r=c.get('/api/analytics?q=HDPE+soplado+MI+0.35&grain=day')
            assert r.status_code==200 and r.json()['metrics']['series']==1
            assert c.get('/api/analytics?material=PP').json()['metrics']['series']==0
            assert c.get('/api/analytics?grain=year').status_code==422
            assert c.get('/api/analytics?start=2026-10-01&end=2026-09-01').status_code==422
            assert c.get('/api/analytics?start=1900-01-01').status_code==422
            assert c.get('/api/analytics?compare_start=2026-08-24').status_code==422
            export=c.get('/api/analytics/export?grain=week')
            assert export.status_code==200 and export.content.startswith(b'\xef\xbb\xbf')
            assert 'backed_days' in export.text and '27690.570000' in export.text
    finally: app.dependency_overrides.clear()


def test_empty_history(db):
    result=history(db,Filters(),conditions)
    assert result['timeline']==[] and result['metrics'] is None


def test_calendar_month_and_week_edges():
    assert bucket_start(date(2026,9,1),'week')==date(2026,8,31)
    assert bucket_end(date(2024,2,1),'month')==date(2024,2,29)


def test_failed_run_keeps_every_committed_checkpoint(db,raw,artifact,monkeypatch):
    from radar import etl,sources
    maker=sessionmaker(db.get_bind(),expire_on_commit=False)
    monkeypatch.setattr(etl,'Session',maker)
    periods=[{'start':str(date(2026,8,3)+timedelta(weeks=n)),'end':str(date(2026,8,9)+timedelta(weeks=n))} for n in range(3)]
    pairs=[{'ma':'ma'+str(n),'mb':'mb'+str(n),'period':p} for n,p in enumerate(periods)]
    monkeypatch.setattr(sources,'discover',lambda:list(reversed(pairs)))
    monkeypatch.setattr(sources,'download',lambda url,source,period,force:dict(artifact,period=period))
    def rows(ma,mb,scope):
        if ma['period']==periods[2]: raise RuntimeError('Download interrupted')
        yield {**normalize_ma(dict(raw,NUME_CORRE=ma['period']['end'].replace('-',''))),'artifact_id':artifact['id']}
    monkeypatch.setattr(sources,'bulk_rows',rows)
    run_id=etl.create_run('bulk',{'weeks':3})
    with pytest.raises(RuntimeError,match='interrupted'): etl._execute_run(run_id)
    with maker() as s:
        run=s.get(Run,run_id)
        assert run.status=='failed' and set(run.result)=={p['end'] for p in periods[:2]}
        assert s.scalar(select(func.count()).select_from(Operation))==2
