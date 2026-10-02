import hashlib
import json
import re
import time
import zipfile
import shutil
from datetime import date, timedelta, datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from dbfread import DBF, FieldParser
from radar.config import settings
from radar.normalize import code, relevant, normalize_ma

INDEX_URL = "http://www.aduanet.gob.pe/aduanas/informae/presentacion_bases_web.htm"
QUERY_URL = "http://www.aduanet.gob.pe/cl-ad-consdepa/ConsImpoIAServlet?accion=cargarConsulta&tipoConsulta=14"

def archive_period(filename):
    m = re.fullmatch(r"(?:ma|mb|mam)(\d{2})(\d{2})(\d{2})(\d{2})\.zip",filename,re.I)
    if not m: raise ValueError("Nombre semanal no reconocido")
    start_day,end_day,month,year = map(int,m.groups())
    end = date(2000+year,month,end_day)
    start = end-timedelta(days=6)
    if start.day != start_day: raise ValueError("Período semanal inconsistente")
    return {"start":start.isoformat(),"end":end.isoformat(),"meaning":"ventana de publicación, puede incluir rectificaciones de otras fechas"}

def discover():
    with httpx.Client(timeout=60,follow_redirects=True) as client:
        response = client.get(INDEX_URL);response.raise_for_status()
    soup = BeautifulSoup(response.content,"html.parser")
    pairs = {}
    for link in soup.select("a[href]"):
        url = urljoin(INDEX_URL,link["href"].replace('\\','/'))
        name = Path(urlparse(url).path).name.lower()
        if re.fullmatch(r"m[ab]\d{8}\.zip",name):
            if urlparse(url).hostname != "www.aduanet.gob.pe": continue
            try: period=archive_period(name)
            except ValueError: continue
            pairs.setdefault(name[2:],{"period":period})[name[:2]]=url
    return sorted([v for v in pairs.values() if "ma" in v and "mb" in v],key=lambda x:x["period"]["end"],reverse=True)

def download(url, source, period, force=False):
    """Resume byte ranges only against the same validator; checksum-complete files are reused."""
    if urlparse(url).hostname not in {"www.aduanet.gob.pe","www.sunat.gob.pe"}: raise ValueError("Fuente no autorizada")
    key=hashlib.sha256(url.encode()).hexdigest()[:16]
    folder=settings.raw_dir/key;folder.mkdir(parents=True,exist_ok=True)
    path=folder/Path(urlparse(url).path).name
    manifest=folder/"manifest.json"
    if manifest.exists() and not force:
        meta=json.loads(manifest.read_text())
        stored=Path(meta['path'])
        if stored.exists() and hashlib.sha256(stored.read_bytes()).hexdigest()==meta["id"]: return meta
    part=path.with_suffix(path.suffix+".part")
    validator_file=folder/"validator.json"
    for attempt in range(3):
        try:
            prior=json.loads(validator_file.read_text()) if validator_file.exists() else {}
            offset=part.stat().st_size if part.exists() and prior.get("validator") else 0
            headers={"Range":f"bytes={offset}-","If-Range":prior["validator"]} if offset else {}
            with httpx.Client(timeout=120,follow_redirects=True) as client, client.stream("GET",url,headers=headers) as response:
                response.raise_for_status()
                if response.status_code==206 and not response.headers.get("Content-Range","").startswith(f"bytes {offset}-"):
                    raise ValueError("Rango HTTP inesperado")
                append=offset>0 and response.status_code==206
                validator=response.headers.get("etag") or response.headers.get("last-modified")
                validator_file.write_text(json.dumps({"validator":validator}))
                with part.open("ab" if append else "wb") as out:
                    for chunk in response.iter_bytes(): out.write(chunk)
            if path.suffix.lower()==".zip":
                with zipfile.ZipFile(part) as z:
                    if z.testzip(): raise ValueError("CRC ZIP inválido")
            part.replace(path)
            return register_file(path,source,url,period,manifest)
        except (httpx.HTTPError, ValueError, zipfile.BadZipFile):
            if attempt==2: raise
            time.sleep(2**attempt)

def register_file(path,source,url,period,manifest=None):
    path=Path(path)
    checksum=hashlib.sha256(path.read_bytes()).hexdigest()
    immutable=settings.raw_dir/'objects'/checksum/(path.name)
    immutable.parent.mkdir(parents=True,exist_ok=True)
    if immutable.resolve()!=path.resolve():
        if immutable.exists() and hashlib.sha256(immutable.read_bytes()).hexdigest()!=checksum:
            raise ValueError('Original conservado corrupto: '+str(immutable))
        if not immutable.exists(): shutil.copy2(path,immutable)
    meta={"id":checksum,"source":source,"url":url,"path":str(immutable.resolve()),"period":period,"bytes":path.stat().st_size,"downloaded_at":datetime.now(timezone.utc).isoformat()}
    (manifest or path.with_suffix(path.suffix+".json")).write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    return meta

class DecimalParser(FieldParser):
    def parseN(self,field,data):
        data=data.strip().strip(b"\x00")
        if not data: return None
        return Decimal(data.decode("ascii"))

def open_dbf(artifact):
    path=Path(artifact["path"])
    with zipfile.ZipFile(path) as z:
        names=[n for n in z.namelist() if n.lower().endswith(".dbf")]
        if len(names)!=1: raise ValueError("Se esperaba un único DBF")
        info=z.getinfo(names[0])
        if info.file_size>2_000_000_000: raise ValueError("DBF excede límite de 2 GB")
        target=path.parent/(artifact["id"][:12]+".dbf")
        if not target.exists() or target.stat().st_size!=info.file_size:
            with z.open(names[0]) as src, target.open("wb") as dst: shutil.copyfileobj(src,dst)
    return DBF(str(target),encoding="cp1252",char_decode_errors="replace",parserclass=DecimalParser)

def row_key(r,series="NUME_SERIE"):
    return (code(r["CODI_ADUAN"],3),code(r["ANO_PRESE"])[-2:],code(r["NUME_CORRE"],6),int(code(r[series])))

def bulk_rows(ma,mb,scope="plastics"):
    table=open_dbf(ma)
    required={"CODI_ADUAN","ANO_PRESE","NUME_CORRE","NUME_SERIE","FOB_DOLPOL","PESO_NETO","DNOMBRE","PART_NANDI"}
    if not required.issubset(table.field_names): raise ValueError("Esquema MA cambió; carga detenida")
    selected={}
    for row in table:
        description=" ".join(str(row.get(k) or "") for k in ["DESC_COMER","DESC_MATCO","DESC_USOAP","DESC_FOPRE","DESC_OTROS"])
        if scope=="plastics" and not relevant(code(row["PART_NANDI"],10),description): continue
        key=row_key(row)
        previous=selected.get(key)
        if previous is None or code(row.get("FMOD")) >= code(previous.get("FMOD")): selected[key]=row
    suppliers={}
    mbtable=open_dbf(mb)
    if not {"NUME_ITEM","NOMB_PROVE","VFOB_ITEM"}.issubset(mbtable.field_names): raise ValueError("Esquema MB cambió")
    for row in mbtable:
        key=row_key(row,"NUME_ITEM")
        if key in selected: suppliers.setdefault(key,[]).append(row)
    for key,row in selected.items():
        result=normalize_ma(row,suppliers.get(key))
        result["raw"]["mb_artifact_id"]=mb["id"]
        from radar.normalize import fingerprint
        result["record_hash"]=fingerprint(result["raw"])
        result["artifact_id"]=ma["id"]
        yield result
