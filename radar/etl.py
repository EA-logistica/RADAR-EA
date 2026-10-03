import logging
import hashlib
from datetime import datetime, date
from uuid import uuid4
from sqlalchemy import select, text, func
from sqlalchemy.dialects.postgresql import insert
from radar.db import Session, engine
from radar.models import Operation, Artifact, Revision, Run, Alert, now
from radar.normalize import fingerprint, text as normalize_text
from radar.config import settings

log=logging.getLogger('radar')
KEY=['country','regime','customs','year','declaration','series']

def save_artifacts(session, artifacts):
    for a in artifacts:
        values={**a,'downloaded_at':datetime.fromisoformat(a['downloaded_at'])}
        session.execute(insert(Artifact).values(**values).on_conflict_do_nothing(index_elements=['id']))

def alert_for(session, op, prior_max):
    # Backfills are baseline, not evidence of a newly arriving shipment.
    if prior_max is None or op.numbered_on<=prior_max: return
    def add(kind,title,detail):
        session.execute(insert(Alert).values(fingerprint=f'{kind}:{op.id}',kind=kind,operation_id=op.id,title=title,detail=detail).on_conflict_do_nothing(index_elements=['fingerprint']))
    add('new_operation',f'Nueva operación: {op.importer or op.importer_ruc or "importador sin identificar"}',{'date':str(op.numbered_on),'material':op.material,'meaning':'Nueva en la cobertura cargada; fecha de numeración'})
    prior=select(Operation).where(Operation.importer_ruc==op.importer_ruc,Operation.numbered_on<op.numbered_on)
    if not op.importer_ruc: return
    if op.supplier and session.scalar(prior.where(Operation.supplier==op.supplier).limit(1)) is None:
        add('new_supplier',f'Nuevo proveedor observado: {op.supplier}',{'importer':op.importer,'coverage_limited':True})
    previous=session.scalar(prior.where(Operation.hs_code==op.hs_code,Operation.description==op.description,Operation.supplier==op.supplier,Operation.origin==op.origin).order_by(Operation.numbered_on.desc(),Operation.id.desc()).limit(1))
    if previous:
        for kind,field,threshold,label in [('price_change','usd_kg',settings.alert_price_percent,'precio FOB USD/kg'),('volume_change','net_kg',settings.alert_volume_percent,'volumen de serie')]:
            old,new=getattr(previous,field),getattr(op,field)
            if old and old>0 and new and new>0:
                change=float((new-old)/old*100)
                if abs(change)>=threshold:
                    add(kind,f'Variación de {label}: {change:+.1f}%',{'previous_operation_id':previous.id,'previous':str(old),'current':str(new),'percent':change,'threshold':threshold,'method':'Misma descripción literal, importador, subpartida, origen y proveedor; no certifica equivalencia técnica.'})

_CURRENT = object()

def load(session, artifacts, rows, baseline=_CURRENT):
    # A transaction-scoped advisory lock serializes upserts, revisions and baseline alerts.
    session.execute(text('SELECT pg_advisory_xact_lock(7242301)'))
    save_artifacts(session,artifacts)
    prior_max=session.scalar(select(func.max(Operation.numbered_on))) if baseline is _CURRENT else baseline
    counts={'inserted':0,'updated':0,'unchanged':0,'older_ignored':0}
    for values in rows:
        if not values.get('importer') and values.get('importer_ruc'):
            reference=session.scalar(select(Operation).where(Operation.importer_ruc==values['importer_ruc'],Operation.source_priority==20,Operation.importer.is_not(None)).order_by(Operation.numbered_on.desc(),Operation.id.desc()).limit(1))
            if reference:
                values['importer']=reference.importer
                values['search_text']+=' '+normalize_text(reference.importer)
                values['raw']={**values['raw'],'_enrichment':{'importer_name':reference.importer,'exact_ruc':reference.importer_ruc,'reference_operation_id':reference.id,'reference_artifact_id':reference.artifact_id}}
                values['record_hash']=fingerprint(values['raw'])
        existing=session.scalar(select(Operation).where(*(getattr(Operation,k)==values[k] for k in KEY)))
        if existing:
            # Retain every observed raw variant, even when it is lower priority or older.
            session.execute(insert(Revision).values(operation_id=existing.id,artifact_id=values['artifact_id'],record_hash=values['record_hash'],raw=values['raw']).on_conflict_do_nothing(constraint='uq_revision'))
            if existing.record_hash==values['record_hash']:
                counts['unchanged']+=1;continue
            if values['source_priority']<existing.source_priority or (existing.source_modified_on and values.get('source_modified_on') and values['source_modified_on']<existing.source_modified_on):
                counts['older_ignored']+=1;continue
            for k,v in values.items():
                if existing.classification_locked and k in {'material','needs_review','classification_reason'}: continue
                setattr(existing,k,v)
            existing.updated_at=now();counts['updated']+=1
        else:
            existing=Operation(**values);session.add(existing);session.flush()
            session.add(Revision(operation_id=existing.id,artifact_id=values['artifact_id'],record_hash=values['record_hash'],raw=values['raw']))
            alert_for(session,existing,prior_max);counts['inserted']+=1
    session.commit()
    from radar.grades import apply as apply_grades
    counts.update(apply_grades(session,only_missing=counts['updated']==0))
    return counts

def create_run(kind, parameters, status='queued'):
    with Session() as s:
        run=Run(id=str(uuid4()),kind=kind,parameters=parameters,status=status);s.add(run);s.commit();return run.id

def execute_run(run_id):
    # CLI and worker can see the same run. Hold a dedicated connection lock across
    # downloads and transaction commits so they never write the same checkpoint together.
    key=int.from_bytes(hashlib.sha256(run_id.encode()).digest()[:8],byteorder='big',signed=True)
    with engine.connect() as lock:
        if not lock.scalar(text('SELECT pg_try_advisory_lock(:key)'),{'key':key}):
            return {'status':'running','id':run_id}
        try: return _execute_run(run_id)
        finally: lock.execute(text('SELECT pg_advisory_unlock(:key)'),{'key':key})

def _execute_run(run_id):
    from radar.sources import discover, download, bulk_rows
    from radar.scraper import scrape
    with Session() as s:
        run=s.get(Run,run_id)
        if run.status=='completed': return run.result
        run.status='running';run.error=None;s.commit()
        try:
            p=dict(run.parameters)
            if '_baseline_date' not in p:
                baseline=s.scalar(select(func.max(Operation.numbered_on)))
                p['_baseline_date']=baseline.isoformat() if baseline else None
                run.parameters=p;s.commit()
            baseline=date.fromisoformat(p['_baseline_date']) if p['_baseline_date'] else None
            result={}
            if run.kind=='bulk':
                available=discover()
                if not available: raise ValueError('No hay archivos semanales verificados')
                weeks=p.get('weeks',1)
                selected=[x for x in available if not p.get('end') or x['period']['end']<=p['end']][:weeks]
                if not selected: raise ValueError('Sin archivos para ese período')
                # Oldest first supports chronological alerts. Each archive pair is an atomic checkpoint.
                for pair in reversed(selected):
                    ma=download(pair['ma'],'sunat_ma',pair['period'],p.get('force',False));mb=download(pair['mb'],'sunat_mb',pair['period'],p.get('force',False))
                    log.info('bulk_parse %s',pair['period'])
                    counts=load(s,[ma,mb],bulk_rows(ma,mb,p.get('scope','plastics')),baseline)
                    result[pair['period']['end']]=counts
                    # JSON columns need a fresh value after every committed window.
                    run.result=dict(result);s.commit()
            elif run.kind=='query':
                artifacts,rows=scrape(p['kind'],p['value'],p['start'],p['end'],p.get('force',False))
                result=load(s,artifacts,rows,baseline)
            elif run.kind=='reprocess':
                from radar.normalize import normalize_ma, NORMALIZER_VERSION
                rows=[]
                for op in s.scalars(select(Operation)):
                    normalized=normalize_ma(op.raw['ma'],op.raw.get('mb_candidates'))
                    normalized['raw']={**op.raw,'_transform_version':NORMALIZER_VERSION}
                    normalized['record_hash']=fingerprint(normalized['raw'])
                    normalized['source_priority']=op.source_priority
                    normalized['artifact_id']=op.artifact_id
                    rows.append(normalized)
                result=load(s,[],rows,baseline=None)
            else: raise ValueError('Tipo de ejecución desconocido')
            run.status='completed';run.finished_at=now();run.result=result;s.commit()
            log.info('run_completed %s %s',run.id,result);return result
        except Exception as e:
            s.rollback();run=s.get(Run,run_id);run.status='failed';run.finished_at=now();run.error=str(e)[:3000];s.commit()
            log.exception('run_failed %s',run_id);raise
