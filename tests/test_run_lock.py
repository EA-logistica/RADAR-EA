from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4
from radar import etl

def test_cli_worker_cannot_execute_same_run(db,monkeypatch):
    monkeypatch.setattr(etl,'engine',db.get_bind())
    entered=Event();release=Event();calls=[]
    def work(run_id):
        calls.append(run_id);entered.set();release.wait(5);return {'completed':True}
    monkeypatch.setattr(etl,'_execute_run',work)
    run_id=str(uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(etl.execute_run,run_id)
        assert entered.wait(3)
        try: assert etl.execute_run(run_id)=={'status':'running','id':run_id}
        finally: release.set()
        assert first.result()=={'completed':True}
    assert calls==[run_id]
