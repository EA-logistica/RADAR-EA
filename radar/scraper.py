"""Official detailed consultation. Uses browser session, pagination and original export."""
import hashlib
import json
import re
import time
from datetime import date, timedelta
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from radar.config import settings
from radar.sources import QUERY_URL, register_file
from radar.normalize import normalize_ma, fingerprint, text, NORMALIZER_VERSION

class SourceBlocked(RuntimeError): pass

HEADERS = ['Declaración','Importador','Fec. Numeración','Agencia','Series','FOB US$','Flete US$','Seguro','Almacén','Canal','Peso Neto','Nro. Bultos','Serie','Partida','Desc. Comer','Desc. Present','Desc. Mat. Const','Desc. Uso','Desc. Otros','cantidad','Unid','Pais Adq.','Pais Orig.','Peso Neto','FOB','Flete','Seguro','ADV','IGV','ISC','IPM','DER. ESP','DER. ANT','IPM. ADIC','COMMOD']

def parse_html(html):
    soup=BeautifulSoup(html,'html.parser')
    visible=text(soup.get_text(' ',strip=True))
    if any(x in visible for x in ['CAPTCHA','CODIGO QUE SE MUESTRA EN LA IMAGEN','ACCESS DENIED','ACCESO DENEGADO']):
        raise SourceBlocked('Control de acceso detectado; requiere consulta humana')
    for tr in soup.select('tr'):
        headers=[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'],recursive=False)]
        if headers and text(headers[0])=='DECLARACION':
            if [text(h) for h in headers]!=[text(h) for h in HEADERS]: raise ValueError('Esquema web cambió; revisar adaptador')
            rows=[]
            for row in tr.parent.find_all('tr',recursive=False):
                cells=row.find_all('td',recursive=False)
                values=[c.get_text(' ',strip=True) for c in cells]
                if not values or not re.fullmatch(r'\d{3}-\d{2,4}-\d+',values[0]): continue
                if len(values)!=35: raise ValueError('Serie con columnas incompletas')
                customs,year,decl=values[0].split('-')
                doc=values[1].split('-',1)
                raw=dict(CODI_ADUAN=customs,ANO_PRESE=year,NUME_CORRE=decl,FECH_INGSI=values[2],TIPO_DOCUM=doc[0],LIBR_TRIBU=doc[-1],NUME_SERIE=values[12],PART_NANDI=values[13],DESC_COMER=values[14],DESC_FOPRE=values[15],DESC_MATCO=values[16],DESC_USOAP=values[17],DESC_OTROS=values[18],UNID_FIQTY=values[19],UNID_FIDES=values[20],PAIS_ADQUI=values[21],PAIS_ORIGE=values[22],PESO_NETO=values[23],FOB_DOLPOL=values[24],FLE_DOLAR=values[25],SEG_DOLAR=values[26])
                result=normalize_ma(raw)
                result['raw']={'web_headers':HEADERS,'web_values':values,'ma':raw,'_transform_version':NORMALIZER_VERSION}
                result['record_hash']=fingerprint(result['raw']);result['source_priority']=10
                rows.append(result)
            total=re.search(r'\b(\d+)\s+A\s+(\d+)\s+DE\s+(\d+)\b',visible)
            if not total: raise ValueError('No se pudo verificar total de resultados')
            return rows,int(total[3])
    if any(x in visible for x in ['NO SE ENCONTRARON','NO EXISTEN REGISTROS','NO SE ENCONTRO','SIN RESULTADOS']): return [],0
    raise ValueError('Sin tabla ni respuesta vacía verificable; no se marca como completado')

def scrape(kind, value, start, end, force=False):
    expected=11 if kind=='importer' else 10
    if not re.fullmatch(r'\d{'+str(expected)+'}',value): raise ValueError('Código inválido')
    start,end=date.fromisoformat(start),date.fromisoformat(end)
    if end<start or (end-start).days>366: raise ValueError('Rango permitido: hasta 367 días')
    artifacts=[];all_rows=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(accept_downloads=True)
        page=context.new_page();page.set_default_timeout(30000)
        while start<=end:
            stop=min(start+timedelta(days=6),end)
            period={'start':start.isoformat(),'end':stop.isoformat(),'kind':kind,'value':value}
            folder=settings.raw_dir/'queries'/fingerprint(period)[:20];folder.mkdir(parents=True,exist_ok=True)
            checkpoint=folder/'complete.json'
            cached=json.loads(checkpoint.read_text()) if checkpoint.exists() and not force else None
            if cached and all(Path(a['path']).exists() and hashlib.sha256(Path(a['path']).read_bytes()).hexdigest()==a['id'] for a in cached['artifacts']):
                for a in cached['artifacts']:
                    artifacts.append(a)
                    if a['source']=='sunat_query_html':
                        rows,_=parse_html(Path(a['path']).read_text(encoding='utf-8'))
                        for r in rows: r['artifact_id']=a['id']
                        all_rows.extend(rows)
                start=stop+timedelta(days=1);continue
            error=None
            for attempt in range(3):
                try:
                    page.goto(QUERY_URL,wait_until='domcontentloaded')
                    page.locator('[name=fec_inicio]').fill(start.strftime('%d/%m/%Y'))
                    page.locator('[name=fec_fin]').fill(stop.strftime('%d/%m/%Y'))
                    page.locator('select[name=tipo]').select_option('1' if kind=='importer' else '5')
                    page.locator('[name=documento]').fill(value)
                    with page.expect_navigation(wait_until='domcontentloaded'): page.locator('[name=btnConsultar]').click()
                    window_rows=[];window_artifacts=[];seen=set();page_no=0;total=None
                    while True:
                        html=page.content();rows,reported=parse_html(html)
                        if total is not None and total!=reported: raise ValueError('Total cambió durante paginación; reintentar ventana')
                        total=reported
                        sig=fingerprint([r['record_hash'] for r in rows])
                        if sig in seen: raise ValueError('Paginación repetida')
                        seen.add(sig)
                        path=folder/f'page-{page_no:04}.html';path.write_text(html,encoding='utf-8')
                        a=register_file(path,'sunat_query_html',QUERY_URL,period);window_artifacts.append(a)
                        for r in rows: r['artifact_id']=a['id']
                        window_rows.extend(rows)
                        next_link=page.get_by_role('link',name='Siguiente',exact=True)
                        if next_link.count()==0: break
                        time.sleep(settings.scrape_delay_seconds)
                        with page.expect_navigation(wait_until='domcontentloaded'): next_link.click()
                        page_no+=1
                        if page_no>1000: raise ValueError('Límite de páginas alcanzado; reducir ventana')
                    if len(window_rows)!=total: raise ValueError(f'Cobertura incompleta: {len(window_rows)}/{total}')
                    # Preserve original export independently of parser output.
                    export=page.get_by_role('link',name='Excel',exact=True)
                    if total and export.count():
                        with page.expect_download(timeout=60000) as event: export.click()
                        download=event.value;path=folder/('export'+(Path(download.suggested_filename).suffix or '.xls'))
                        download.save_as(path)
                        window_artifacts.append(register_file(path,'sunat_query_export',QUERY_URL,period))
                    checkpoint.write_text(json.dumps({'artifacts':window_artifacts,'rows':total},ensure_ascii=False,indent=2),encoding='utf-8')
                    artifacts.extend(window_artifacts);all_rows.extend(window_rows);error=None;break
                except SourceBlocked:
                    (folder/'blocked.html').write_text(page.content(),encoding='utf-8');raise
                except Exception as e:
                    error=e
                    (folder/'error.html').write_text(page.content(),encoding='utf-8')
                    time.sleep(2**attempt)
            if error: raise error
            start=stop+timedelta(days=1)
            time.sleep(settings.scrape_delay_seconds)
        browser.close()
    return artifacts,all_rows
