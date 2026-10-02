"""Deterministic transformations. No fuzzy entity merges or guessed bag weights."""
import hashlib
import json
import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation
import pycountry

MATERIALS = ["HDPE", "LDPE", "LLDPE", "PE", "PP", "PET", "Masterbatch", "Aditivos", "Otros", "Revisar"]
NORMALIZER_VERSION = '2'
MISSING = {"", "NO DISPONIBLE", "NO DISPONI", "S/N", "S/M", "N/A", "NULL", "NONE", "0"}

def text(value):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()).strip().upper()

def entity(value):
    v = text(value)
    return None if v in MISSING else v

def number(value):
    if value is None or str(value).strip() in ("", "-", "N/A"): return None
    try:
        result = Decimal(str(value).strip().replace(",", ""))
        return result if result.is_finite() else None
    except InvalidOperation: return None

def code(value, width=0):
    s = str(value or "").strip()
    if re.fullmatch(r"\d+\.0+", s): s = s.split(".")[0]
    return s.zfill(width)

def date_value(value):
    if not value: return None
    s = code(value)
    for fmt in ("%Y%m%d", "%d/%m/%Y", "%Y-%m-%d"):
        try: return datetime.strptime(s, fmt).date()
        except ValueError: pass
    return None

def country(value):
    v = entity(value)
    if not v: return None
    aliases = {"ESTADOS UNIDOS":"US", "EEUU":"US", "CHINA":"CN", "BRASIL":"BR", "COREA DEL SUR":"KR", "ARABIA SAUDITA":"SA", "PERU":"PE"}
    v = aliases.get(v, v)
    if len(v) == 2 and pycountry.countries.get(alpha_2=v): return v
    if len(v) == 3:
        found = pycountry.countries.get(alpha_3=v) or pycountry.countries.get(numeric=v)
        if found: return found.alpha_2
    return None

def classify(hs, description):
    d = text(description)
    if hs.startswith('390130') or re.search(r'\bEVA\b|ETILENO.?ACETATO DE VINILO|\bPETG\b',d):
        return 'Otros', True, 'Copolímero EVA o PETG: revisar como material relacionado, sin equipararlo a PE/PET.'
    candidates = []
    rules = [("Masterbatch",r"\bMASTER\s?BATCH\b|CONCENTRADO (?:DE )?(?:COLOR|PIGMENTO)"),
             ("LLDPE",r"\bLLDPE\b|LINEAR LOW DENSITY|BAJA DENSIDAD LINEAL"),
             ("HDPE",r"\bHDPE\b|\bPEAD\b|HIGH DENSITY POLYETHYLENE|POLIETILENO (?:DE )?ALTA DENSIDAD"),
             ("LDPE",r"\bLDPE\b|\bPEBD\b|(?<!LINEAR )LOW DENSITY POLYETHYLENE|POLIETILENO (?:DE )?BAJA DENSIDAD(?! LINEAL)"),
             ("PP",r"\bPP\b|POLIPROPILENO|POLYPROPYLENE"),
             ("PET",r"\bPET\b|POLYETHYLENE TEREPHTHALATE|TEREFTALATO DE POLIETILENO"),
             ("Aditivos",r"\bADITIVO\b|\bADDITIVE\b|ANTIOXIDANTE|ESTABILIZANTE|PLASTIFICANTE")]
    for material, pattern in rules:
        if re.search(pattern,d): candidates.append(material)
    if "Masterbatch" in candidates:
        return "Masterbatch", False, "Descripción explícita de masterbatch; resina portadora no implica equivalencia."
    if "Aditivos" in candidates:
        return "Aditivos", True, "Aditivo declarado; revisar función y composición."
    hs_material = "HDPE" if hs.startswith("390120") else "PE" if hs.startswith("3901") else "PP" if hs.startswith("390210") else "PET" if hs.startswith(("390760","390761","390769")) else None
    if len(candidates) > 1: return "Revisar", True, "Varias familias mencionadas: " + ", ".join(candidates)
    if candidates:
        m = candidates[0]
        conflict = hs_material is not None and hs_material != m and not (hs_material == "PE" and m in ("LDPE","LLDPE","HDPE"))
        return ("Revisar",True,"Conflicto entre descripción y subpartida") if conflict else (m,False,"Coincidencia explícita en descripción" )
    if hs_material: return hs_material, True, "Familia inferida por subpartida; revisar descripción/uso."
    return "Revisar", True, "Clasificación insuficiente; revisión requerida."

def relevant(hs, description):
    return hs.startswith(("3901","3902","390760","390761","390769","3812")) or (hs.startswith(('28','29','32','34','38','39')) and bool(re.search(r"MASTER\s?BATCH|ADITIVO.*PLAST|CONCENTRADO (?:DE )?(?:COLOR|PIGMENTO)", text(description))))

def kilograms(quantity, unit, net_weight=None):
    net = number(net_weight)
    if net is not None and net > 0: return net, "Peso neto de la serie en kg (SUNAT)"
    q = number(quantity)
    factors = {"KG":Decimal(1),"KGS":Decimal(1),"KGM":Decimal(1),"KILOGRAMO":Decimal(1),"TM":Decimal(1000),"TNE":Decimal(1000),"TONELADA":Decimal(1000),"G":Decimal("0.001"),"GRM":Decimal("0.001"),"LB":Decimal("0.45359237")}
    u = text(unit)
    if q is None or q <= 0 or u not in factors: return None, None
    return q*factors[u], f"Unidad {u}; factor exacto {factors[u]} kg/{u}"

def price(fob, kg, currency="USD", same_series=True):
    f, k = number(fob), number(kg)
    return f/k if same_series and currency == "USD" and f is not None and f > 0 and k is not None and k > 0 else None

def serializable(obj):
    return json.loads(json.dumps(obj, default=str, ensure_ascii=False))

def fingerprint(obj):
    return hashlib.sha256(json.dumps(serializable(obj), sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def search_groups(query):
    """All concepts must match; synonyms within a concept use OR. Decimals remain intact."""
    q = text(query).replace(",", ".")
    aliases = {"HDPE":["HDPE","PEAD","HIGH DENSITY POLYETHYLENE","POLIETILENO DE ALTA DENSIDAD"],
               "LDPE":["LDPE","PEBD","LOW DENSITY POLYETHYLENE","POLIETILENO DE BAJA DENSIDAD"],
               "LLDPE":["LLDPE","LINEAR LOW DENSITY","BAJA DENSIDAD LINEAL"],
               "PP":["PP","POLIPROPILENO","POLYPROPYLENE"],
               "SOPLADO":["SOPLADO","BLOW MOLDING","BLOW MOULDING"],
               "INYECCION":["INYECCION","INJECTION"],"MI":["MI","MFI","MELT INDEX","INDICE DE FLUIDEZ"]}
    return [aliases.get(token,[token]) for token in re.findall(r"[A-Z0-9]+(?:[.\-/][A-Z0-9]+)*",q)]

def normalize_ma(raw, supplier_rows=None):
    r = raw
    hs = code(r.get("PART_NANDI"),10)
    description = " | ".join(str(r.get(k) or "").strip() for k in ["DESC_COMER","DESC_FOPRE","DESC_MATCO","DESC_USOAP","DESC_OTROS"] if r.get(k))
    material, review, reason = classify(hs,description)
    year = int(code(r["ANO_PRESE"]))
    if year < 100: year += 2000 if year < 70 else 1900
    numbered_on = date_value(r.get("FECH_INGSI"))
    if numbered_on is None: raise ValueError("Fecha de numeración inválida")
    kg, method = kilograms(r.get("UNID_FIQTY"),r.get("UNID_FIDES"),r.get("PESO_NETO"))
    fob,freight,insurance = (number(r.get(k)) for k in ["FOB_DOLPOL","FLE_DOLAR","SEG_DOLAR"])
    flags = []
    if kg is None: flags.append("sin_kg_verificables")
    if fob is None or fob <= 0: flags.append("sin_valor_comparable")
    origin = country(r.get("PAIS_ORIGE"))
    if origin is None: flags.append("origen_no_normalizado")
    suppliers = supplier_rows or []
    names = {entity(x.get("NOMB_PROVE")) for x in suppliers}
    names.discard(None)
    sum_fob = sum((number(x.get("VFOB_ITEM")) or Decimal(0) for x in suppliers),Decimal(0))
    matched = suppliers and all(code(x.get("PART_NANDI"),10)==hs for x in suppliers) and fob is not None and abs(sum_fob-fob)<=max(Decimal("0.02"),abs(fob)*Decimal("0.001"))
    supplier = next(iter(names)) if matched and len(names)==1 and all(entity(x.get("NOMB_PROVE")) for x in suppliers) else None
    supplier_status = "verified_match" if supplier else "redacted" if suppliers and not names else "ambiguous" if suppliers else "unavailable"
    if not supplier: flags.append("proveedor_"+supplier_status)
    original = {"ma":r,"mb_candidates":suppliers,"_transform_version":NORMALIZER_VERSION}
    customs,declaration,series = code(r["CODI_ADUAN"],3),code(r["NUME_CORRE"],6),int(code(r["NUME_SERIE"]))
    importer = entity(r.get("DNOMBRE"))
    doc = code(r.get("LIBR_TRIBU"))
    ruc = doc if code(r.get("TIPO_DOCUM"))=="4" and re.fullmatch(r"\d{11}",doc) else None
    return dict(country="PE",regime="10",customs=customs,year=year,declaration=declaration,series=series,
        numbered_on=numbered_on,importer_ruc=ruc,importer=importer,supplier=supplier,supplier_status=supplier_status,
        origin=origin,acquisition_country=country(r.get("PAIS_ADQUI")),hs_code=hs,description=description,
        material=material,classification_reason=reason,needs_review=review,plastics_scope=relevant(hs,description),currency="USD",
        quantity=number(r.get("UNID_FIQTY")),unit=entity(r.get("UNID_FIDES")),net_kg=kg,kg_method=method,
        fob_usd=fob,freight_usd=freight,insurance_usd=insurance,cif_usd=fob+freight+insurance if all(x is not None and x>=0 for x in [fob,freight,insurance]) else None,
        usd_kg=price(fob,kg),search_text=text(" ".join([description,importer or "",ruc or "",supplier or "",material,hs])),
        quality_flags=flags,raw=serializable(original),record_hash=fingerprint(original),source_priority=20,
        source_modified_on=date_value(r.get("FMOD")),source_url=f"http://www.aduanet.gob.pe/servlet/SgCDUI2?codaduana={customs}&numecorre={declaration}&anoprese={year}&option=una&n=10")
