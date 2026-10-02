"""Single durable queue consumer. A process lock prevents overlapping workers."""
import logging
import time
from sqlalchemy import select, text
from radar.db import Session, engine
from radar.models import Run
from radar.etl import execute_run

def main():
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    with engine.connect() as lock:
        if not lock.scalar(text('SELECT pg_try_advisory_lock(7242302)')): raise RuntimeError('Otro worker está activo')
        with Session() as s:
            for r in s.scalars(select(Run).where(Run.status=='running')): r.status='queued'
            s.commit()
        while True:
            with Session() as s:
                run=s.scalar(select(Run).where(Run.status=='queued').order_by(Run.started_at).limit(1))
                run_id=run.id if run else None
            if run_id:
                try:
                    result=execute_run(run_id)
                    if result.get('status')=='running': time.sleep(3)
                except Exception: logging.exception('Ejecución fallida; reanudar desde la interfaz o CLI')
            else: time.sleep(3)

if __name__=='__main__': main()
