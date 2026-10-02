"""Historical metrics over observed series, with explicit source-window coverage."""
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select, func, case, distinct, cast, String
from fastapi import HTTPException
from radar.models import Operation as O, Artifact, Run

D=Decimal

def dates(start,end):
    while start<=end:
        yield start
        start+=timedelta(days=1)

def loaded_windows(s,scope):
    """Artifacts alone do not prove ETL committed. Require the per-week run result too."""
    committed=set()
    for run in s.scalars(select(Run).where(Run.kind=='bulk')):
        if run.parameters.get('scope','plastics') not in ({'plastics','all'} if scope=='plastics' else {'all'}): continue
        committed.update(k for k,v in (run.result or {}).items() if isinstance(v,dict) and 'inserted' in v)
    pairs={}
    for a in s.scalars(select(Artifact).where(Artifact.source.in_(['sunat_ma','sunat_mb']))):
        p=a.period or {}
        if p.get('end') not in committed: continue
        try: start,end=date.fromisoformat(p['start']),date.fromisoformat(p['end'])
        except (KeyError,ValueError): continue
        if not 0<=(end-start).days<=7: continue
        pairs.setdefault((start,end),set()).add(a.source)
    return sorted([{'start':a,'end':b} for (a,b),sources in pairs.items() if sources=={'sunat_ma','sunat_mb'}],key=lambda w:w['start'])

def covered_dates(windows):
    return {d for w in windows for d in dates(w['start'],w['end'])}

def coverage(start,end,covered):
    total=(end-start).days+1
    count=sum(d in covered for d in dates(start,end))
    return {'days':total,'backed_days':count,'backed_percent':round(count/total*100,1),'backed':count==total}

def bucket_start(d,grain):
    if grain=='day': return d
    if grain=='week': return d-timedelta(days=d.weekday())
    return d.replace(day=1)

def bucket_end(d,grain):
    if grain=='day': return d
    if grain=='week': return d+timedelta(days=6)
    return d.replace(day=monthrange(d.year,d.month)[1])

def percentage_change(current,previous,eligible=True):
    if not eligible or current is None or previous is None or previous==0: return None
    return (D(str(current))-D(str(previous)))/abs(D(str(previous)))*100

def declarations():
    return O.country+'-'+O.customs+'-'+cast(O.year,String)+'-'+O.regime+'-'+O.declaration

def metrics(s,c):
    valid=O.usd_kg.is_not(None)
    r=s.execute(select(
        func.count(O.id).label('series'),func.count(distinct(declarations())).label('operations'),
        func.sum(O.fob_usd).label('fob_usd'),(func.sum(O.net_kg)/1000).label('tonnes'),
        func.count(distinct(O.importer_ruc)).label('importers'),func.count(distinct(O.origin)).label('origins'),
        func.count(distinct(O.supplier)).label('suppliers'),
        (func.sum(case((valid,O.fob_usd)))/func.nullif(func.sum(case((valid,O.net_kg))),0)).label('usd_kg'),
        func.percentile_cont(.5).within_group(O.usd_kg).label('median_usd_kg'),
        func.percentile_cont(.25).within_group(O.usd_kg).label('p25_usd_kg'),
        func.percentile_cont(.75).within_group(O.usd_kg).label('p75_usd_kg'),
        func.count(case((valid,1))).label('priced_series'),
        func.count(case((O.net_kg.is_not(None),1))).label('weighed_series'),
        func.count(case((O.fob_usd.is_not(None),1))).label('valued_series'),
        func.count(case((O.needs_review,1))).label('review_series'),
        func.count(distinct(O.numbered_on)).label('active_days')
    ).where(*c)).mappings().one()
    result=dict(r)
    n=result['operations']
    result['ticket_usd']=result['fob_usd']/n if n and result['fob_usd'] is not None else None
    result['tonnes_per_operation']=result['tonnes']/n if n and result['tonnes'] is not None else None
    count=result['series']
    for name,numerator in [('priced_percent','priced_series'),('weighed_percent','weighed_series'),('review_percent','review_series')]:
        result[name]=round(result[numerator]/count*100,1) if count else None
    return result

def timeline(s,c,start,end,grain,covered):
    period=func.date_trunc(grain,O.numbered_on)
    valid=O.usd_kg.is_not(None)
    rows=s.execute(select(period.label('period'),func.sum(O.fob_usd).label('fob_usd'),
        (func.sum(O.net_kg)/1000).label('tonnes'),func.count(O.id).label('series'),
        func.count(distinct(declarations())).label('operations'),func.count(distinct(O.importer_ruc)).label('importers'),
        (func.sum(case((valid,O.fob_usd)))/func.nullif(func.sum(case((valid,O.net_kg))),0)).label('usd_kg'))
        .where(*c,O.numbered_on>=start,O.numbered_on<=end).group_by(period).order_by(period)).mappings()
    grouped={r['period'].date():dict(r) for r in rows}
    cursor=bucket_start(start,grain);result=[];cumulative=D(0);last=None
    while cursor<=end:
        finish=bucket_end(cursor,grain)
        a,b=max(cursor,start),min(finish,end)
        cov=coverage(a,b,covered)
        full=cov['backed'] and a==cursor and b==finish
        row=grouped.get(cursor)
        if row is None:
            row={k:0 if cov['backed'] else None for k in ['fob_usd','tonnes','series','operations','importers']}
            row['usd_kg']=None
        status='backed' if full else 'partial' if row['series'] or cov['backed_days'] else 'missing'
        row.update(period=cursor,end=finish,selection_start=a,selection_end=b,coverage=cov,status=status)
        cumulative+=row['fob_usd'] or D(0)
        row['observed_cumulative_fob']=cumulative
        row['fob_change_percent']=percentage_change(row['fob_usd'],last['fob_usd'],status=='backed' and last['status']=='backed') if last else None
        result.append(row);last=row;cursor=finish+timedelta(days=1)
    return result

def history(s,f,condition_builder,grain='week',compare_start=None,compare_end=None):
    base=condition_builder(f.model_copy(update={'start':None,'end':None}))
    # Bounds are global to the selected catalog, even if a material has no operations.
    scope_condition=[O.plastics_scope.is_(True)] if f.scope=='plastics' else []
    minimum,maximum=s.execute(select(func.min(O.numbered_on),func.max(O.numbered_on)).where(*scope_condition)).one()
    windows=loaded_windows(s,f.scope);covered=covered_dates(windows)
    earliest=min([w['start'] for w in windows]+([minimum] if minimum else []),default=None)
    latest=max([w['end'] for w in windows]+([maximum] if maximum else []),default=None)
    meta={'available_start':earliest,'available_end':latest,'latest_base_end':windows[-1]['end'] if windows else None,'windows':windows,
        'coverage_note':'Ventanas de publicación MA/MB cargadas. Pueden contener rectificaciones; no garantizan exhaustividad nacional por fecha de numeración.',
        'price_note':'FOB/kg ponderado de series comparables; la mezcla de grados puede variar. Mediana y percentiles se calculan por serie, sin ponderación.'}
    if earliest is None and f.start is None:
        return {'meta':meta,'timeline':[],'current':None,'previous':None,'comparison':None,'metrics':None,'movers':[]}
    start=f.start or earliest or f.end
    end=f.end or latest or start
    if not start or not end or end<start: raise HTTPException(422,'Rango histórico inválido')
    if (end-start).days>3660: raise HTTPException(422,'Selecciona un rango de hasta 10 años')
    # Default comparison uses the last 28 source-backed days, avoiding a dangling query day.
    current_end=f.end or (windows[-1]['end'] if windows else end)
    current_start=f.start or max(earliest or start,current_end-timedelta(days=27))
    if current_end<current_start: raise HTTPException(422,'El inicio supera el último período disponible')
    if (compare_start is None)!=(compare_end is None): raise HTTPException(422,'Indica ambas fechas de comparación')
    previous_end=compare_end or current_start-timedelta(days=1)
    previous_start=compare_start or previous_end-timedelta(days=(current_end-current_start).days)
    if previous_end<previous_start or (previous_end-previous_start).days>3660: raise HTTPException(422,'Rango de comparación inválido')
    current_cov=coverage(current_start,current_end,covered);previous_cov=coverage(previous_start,previous_end,covered)
    reasons=[]
    if not current_cov['backed'] or not previous_cov['backed']: reasons.append('Faltan bases semanales en uno de los períodos')
    if current_cov['days']!=previous_cov['days']: reasons.append('Los períodos tienen distinta duración')
    if not (previous_end<current_start or previous_start>current_end): reasons.append('Los períodos se superponen')
    eligible=not reasons
    curr_c=base+[O.numbered_on>=current_start,O.numbered_on<=current_end]
    prev_c=base+[O.numbered_on>=previous_start,O.numbered_on<=previous_end]
    current=metrics(s,curr_c);previous=metrics(s,prev_c)
    delta_keys=['fob_usd','tonnes','operations','importers','usd_kg','ticket_usd']
    deltas={k:percentage_change(current[k],previous[k],eligible) for k in delta_keys}
    groups=list(s.execute(select(O.importer_ruc.label('ruc'),func.max(O.importer).label('name'),
        func.sum(O.fob_usd).label('fob_usd'),func.count(distinct(declarations())).label('operations')).where(*curr_c,O.importer_ruc.is_not(None)).group_by(O.importer_ruc).order_by(func.sum(O.fob_usd).desc().nullslast())).mappings())
    known_value=sum((r['fob_usd'] or D(0) for r in groups),D(0))
    top5=sum((r['fob_usd'] or D(0) for r in groups[:5]),D(0))
    extra={**current,'top5_share_percent':top5/known_value*100 if known_value>0 else None,
        'identified_importer_fob_percent':known_value/current['fob_usd']*100 if current['fob_usd'] and current['fob_usd']>0 else None,
        'repeat_importers':sum(r['operations']>=2 for r in groups)}
    seen=set(s.scalars(select(O.importer_ruc).where(*base,O.numbered_on<current_start,O.importer_ruc.is_not(None)).distinct()))
    extra['first_observed_importers']=sum(r['ruc'] not in seen for r in groups)
    extra['returning_importers']=sum(r['ruc'] in seen for r in groups)
    previous_groups={r['ruc']:r['fob_usd'] for r in s.execute(select(O.importer_ruc.label('ruc'),func.sum(O.fob_usd).label('fob_usd')).where(*prev_c,O.importer_ruc.is_not(None)).group_by(O.importer_ruc)).mappings()}
    movers=[dict(r,previous_fob_usd=previous_groups.get(r['ruc']),change_percent=percentage_change(r['fob_usd'],previous_groups.get(r['ruc']),eligible),share_percent=(r['fob_usd']/known_value*100 if r['fob_usd'] is not None and known_value>0 else None),first_observed=r['ruc'] not in seen) for r in groups[:20]]
    return {'meta':meta,'grain':grain,'timeline':timeline(s,base,start,end,grain,covered),
        'current':{'start':current_start,'end':current_end,'coverage':current_cov,'metrics':current},
        'previous':{'start':previous_start,'end':previous_end,'coverage':previous_cov,'metrics':previous},
        'comparison':{'eligible':eligible,'reasons':reasons,'deltas':deltas,'zero_baseline_note':'Sin porcentaje cuando el valor previo es cero o falta.'},
        'metrics':extra,'movers':movers}
