"""Resumen estructurado de los datos cargados (lectura sola). Uso: python scripts/resumen-datos.py"""
import json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from radar.db import engine

Q = {
    'cobertura': "select count(*) series, count(*) filter (where plastics_scope) plasticos, count(distinct (customs,year,declaration)) filter (where plastics_scope) declaraciones, count(distinct importer_ruc) filter (where plastics_scope) rucs, min(numbered_on) desde, max(numbered_on) hasta, round(sum(fob_usd) filter (where plastics_scope)) fob_usd, round(sum(net_kg) filter (where plastics_scope)/1000) toneladas, count(*) filter (where supplier is not null) con_proveedor, count(*) filter (where needs_review) por_revisar from operations",
    'por_material': "select material, count(*) series, round(sum(fob_usd)) fob_usd, round(sum(net_kg)/1000) t, round(sum(fob_usd)/nullif(sum(net_kg),0),3) usd_kg from operations where plastics_scope group by 1 order by 3 desc nulls last",
    'top_importadores': "select importer_ruc ruc, left(importer,45) importador, count(*) series, round(sum(fob_usd)) fob_usd, round(sum(net_kg)/1000) t from operations where plastics_scope group by 1,2 order by 4 desc nulls last limit 15",
    'top_origen': "select origin, count(*) series, round(sum(fob_usd)) fob_usd, round(sum(net_kg)/1000) t from operations where plastics_scope group by 1 order by 3 desc nulls last limit 10",
    'top_subpartidas': "select hs_code, count(*) series, round(sum(fob_usd)) fob_usd, round(sum(net_kg)/1000) t from operations where plastics_scope group by 1 order by 3 desc nulls last limit 10",
    'por_semana': "select date_trunc('week',numbered_on)::date semana, count(*) series, round(sum(fob_usd)) fob_usd, round(sum(net_kg)/1000) t from operations where plastics_scope group by 1 order by 1",
    'archivos': "select count(*) archivos, round(sum(bytes)/1048576.0,1) mb from artifacts",
}
with engine.connect() as c:
    out = {k: [dict(r._mapping) for r in c.execute(text(q))] for k, q in Q.items()}
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
