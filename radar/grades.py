"""Detección de marca, grado (código de materia prima), aplicación y melt index.

Fuentes, en orden de confianza:
1. Campos estructurados SUNAT: DESC_COMER ("nombre, marca, modelo"), MB MARC_COMER/MODE_MERCD/CARA_TIPO.
2. Texto libre de la serie (descripción, uso, otros).
3. Catálogo de grados (radar/data/grade_catalog.json): ficha técnica de referencia por marca+grado.
El texto declarado tiene prioridad sobre el catálogo para la aplicación; el catálogo aporta nombre completo,
MI y densidad cuando la declaración no los informa. Nada se rellena sin evidencia.
"""
import json
import re
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from radar.normalize import text, MISSING

CATALOG_PATH = Path(__file__).with_name('data') / 'grade_catalog.json'
GRADES_VERSION = '2'

# Alias de texto -> productor / marca canónica. Distribuidores (Muehlstein, Snetor) se registran como tales.
BRANDS = {
    'CERTENE': 'Certene (Muehlstein)', 'MUEHLSTEIN': 'Certene (Muehlstein)',
    'BRASKEM IDESA': 'Braskem Idesa', 'BRASKEM': 'Braskem',
    'DOWLEX': 'Dow', 'ELITE': 'Dow', 'ENGAGE': 'Dow', 'AFFINITY': 'Dow', 'AGILITY': 'Dow', 'INNATE': 'Dow', 'ATTANE': 'Dow',
    'UNIVAL': 'Dow', 'CONTINUUM': 'Dow', 'INFUSE': 'Dow', 'SURLYN': 'Dow', 'ELVAX': 'Dow', 'NORDEL': 'Dow', 'VERSIFY': 'Dow', 'DOW': 'Dow',
    'EXXONMOBIL': 'ExxonMobil', 'EXXON MOBIL': 'ExxonMobil', 'EXXON': 'ExxonMobil', 'EXCEED': 'ExxonMobil', 'ENABLE': 'ExxonMobil',
    'PAXON': 'ExxonMobil', 'EXACT': 'ExxonMobil', 'VISTAMAXX': 'ExxonMobil', 'ESCORENE': 'ExxonMobil', 'ACHIEVE': 'ExxonMobil',
    'LYONDELLBASELL': 'LyondellBasell', 'BASELL': 'LyondellBasell', 'BLYB': 'LyondellBasell', 'MOPLEN': 'LyondellBasell',
    'HOSTALEN': 'LyondellBasell', 'PETROTHENE': 'LyondellBasell', 'ALATHON': 'LyondellBasell', 'LUPOLEN': 'LyondellBasell', 'PRO-FAX': 'LyondellBasell',
    'SABIC': 'SABIC', 'LOTTE CHEMICAL': 'Lotte Chemical', 'LOTTE': 'Lotte Chemical', 'TITANLENE': 'Lotte Chemical', 'TITANPRO': 'Lotte Chemical',
    'ESENTTIA': 'Esenttia', 'PROPILCO': 'Esenttia', 'FORMOLENE': 'Formosa Plastics', 'FORMOSA': 'Formosa Plastics',
    'ICELENE': 'Icelene', 'OSTERLENE': 'Osterlene', 'PETROQUIM': 'Petroquim', 'DAWN': 'Dawn Polymer', 'EASTLON': 'Eastlon (FENC)',
    'SNETOR': 'Snetor (distribuidor)', 'INEOS': 'INEOS', 'BOREALIS': 'Borealis', 'BOROUGE': 'Borouge', 'BORSTAR': 'Borouge',
    'SINOPEC': 'Sinopec', 'PETROCHINA': 'PetroChina', 'HANWHA': 'Hanwha', 'LG CHEM': 'LG Chem', 'SCG': 'SCG Chemicals', 'IRPC': 'IRPC',
    'REPSOL': 'Repsol', 'TOTALENERGIES': 'TotalEnergies', 'TOTAL': 'TotalEnergies', 'MARLEX': 'Chevron Phillips', 'CHEVRON PHILLIPS': 'Chevron Phillips',
    'NOVA CHEMICALS': 'NOVA Chemicals', 'SCLAIR': 'NOVA Chemicals', 'SURPASS': 'NOVA Chemicals', 'POLINTER': 'Polinter', 'VENELENE': 'Polinter',
    'RELIANCE': 'Reliance', 'REPOL': 'Reliance', 'RELENE': 'Reliance', 'HALDIA': 'Haldia', 'OPAL': 'OPaL', 'GAIL': 'GAIL', 'PEMEX': 'Pemex',
    'SASOL': 'Sasol', 'QAPCO': 'QAPCO', 'LOTRENE': 'QAPCO', 'MARUN': 'Marun', 'JAM': 'Jam Petrochemical', 'TASNEE': 'Tasnee', 'SIPCHEM': 'Sipchem',
    'PETRO RABIGH': 'Petro Rabigh', 'YANBU': 'Yansab', 'ORPIC': 'OQ', 'LUBAN': 'OQ', 'HYOSUNG': 'Hyosung', 'TOPILENE': 'Hyosung', 'POLYMIRAE': 'Polymirae',
    'KOREA PETROCHEMICAL': 'KPIC', 'KPIC': 'KPIC', 'DAELIM': 'DL Chemical', 'SK GLOBAL': 'SK geo centric', 'YUHWA': 'KPIC', 'POSCO': 'POSCO (distribuidor)',
    'INDORAMA': 'Indorama', 'JADE': 'Jiangsu Jade (Indorama)', 'WANKAI': 'Wankai', 'CHINA RESOURCES': 'China Resources (CR)', 'CRP': 'China Resources (CR)',
    'SANFAME': 'Sanfame', 'HUARUN': 'China Resources (CR)', 'SAN FANG': 'Sanfame', 'ALPEK': 'Alpek', 'DAK': 'DAK Americas (Alpek)', 'LASER+': 'DAK Americas (Alpek)',
    'NAN YA': 'Nan Ya Plastics', 'NANYA': 'Nan Ya Plastics', 'RAMAPET': 'Indorama', 'POLYTAM': 'Indorama', 'PETRONAS': 'Petronas', 'TITAN': 'Lotte Chemical',
    'EXELENE': 'Exelene (Montachem)', 'MONTACHEM': 'Exelene (Montachem)', 'TOPCOLOR': 'Top Color', 'TOP COLOR': 'Top Color',
    'JINPP': 'Jinpp (Jinneng)', 'JINNENG': 'Jinpp (Jinneng)', 'ROTOLENE': 'Rotolene', 'CYNPOL': 'Cynpol', 'TRICOLENE': 'Tricolene',
    'PRIME POLYMER': 'Prime Polymer', 'EVATANE': 'SK Functional Polymer', 'HIFOR': 'Westlake', 'WESTLAKE': 'Westlake', 'TAISOX': 'Formosa Plastics',
    'YUNGSOX': 'Formosa Plastics', 'TRICOLENE': 'Tricolene', 'SHENHUA': 'China Energy (Shenhua)', 'CYNPOL': 'Cynpol', 'BAOFENG': 'Baofeng',
    'ZHONGTIAN': 'Zhongtian Hechuang', 'HENGLI': 'Hengli', 'ZPC': 'Zhejiang Petrochemical (ZPC)', 'HYUNDAI': 'HD Hyundai Chemical', 'SEETEC': 'Lotte Chemical',
    'KEMYA': 'SABIC', 'BRASKEM MEXICO': 'Braskem Idesa', 'PROPILVEN': 'Propilven', 'PETROKEMYA': 'SABIC', 'TPI': 'TPI Polene', 'POLENE': 'TPI Polene', 'BRASKEM AMERICA': 'Braskem', 'INNOPLUS': 'PTT Global Chemical', 'PTT': 'PTT Global Chemical', 'EL-LENE': 'SCG Chemicals',
}
TRADE_NAMES = sorted(BRANDS, key=len, reverse=True)
CANONICAL_BRANDS = set(BRANDS.values())
BRAND_RE = re.compile(r'(?<![A-Z0-9])(' + '|'.join(re.escape(b) for b in TRADE_NAMES) + r')(?![A-Z0-9])')

# Aplicación / proceso: palabra clave en la declaración -> etiqueta canónica.
APPLICATIONS = [
    ('Soplado', r'(?<!PELICULA )SOPLAD|BLOW ?MOLD|BLOW ?MOULD|FRASCO|BOTELLA|BIDON|GALONERA|BOTTLE'),
    ('Inyección', r'INYECC|INYECT|INJECTION|INJECCION|MOLDEO POR INY'),
    ('Película / film', r'PELICULA|\bFILMS?\b|(?:FABRICA|ELABORA|PRODUC|PARA|ARTICULOS?)[^|]{0,40}BOLSA|BOLSAS? PLASTICA|BOLSAS? DE (?:POLIETILENO|PLASTICO)|EMPAQUES? FLEXIBLE|STRETCH|SHRINK|BLOWN|CAST FILM|LAMINACION'),
    ('Tubería', r'TUBERIA|TUBO|\bPIPE|CONDUIT|MANGUERA'),
    ('Rafia / monofilamento', r'RAFIA|RAFFIA|\bTAPE|MONOFILAMENT|SACOS TEJIDOS|CINTA|HILO|STRAPPING|ZUNCHO'),
    ('Termoformado / lámina', r'TERMOFORM|THERMOFORM|LAMINA|SHEET|PLANCHA'),
    ('Fibra / no tejido', r'FIBRA|FIBER|FIBRE|NO TEJIDO|NONWOVEN|SPUNBOND|MELTBLOWN|MULTIFILAMENT'),
    ('Rotomoldeo', r'ROTOMOLD|ROTOMOULD|ROTACIONAL|TANQUE'),
    ('Cables', r'CABLE|ALAMBRE|AISLAMIENTO|JACKET|XLPE'),
    ('Recubrimiento', r'RECUBRIM|COATING|EXTRUSION COATING'),
    ('Tapas / compresión', r'\bTAPAS?\b|\bCAPS\b|CLOSURE'),
    ('Extrusión', r'EXTRUS|EXTRUD|EXTRUSION'),
]
APP_RES = [(name, re.compile(p)) for name, p in APPLICATIONS]

MI_RE = re.compile(r'(?:\bMI\b|\bMFI\b|\bMFR\b|MELT (?:FLOW )?INDEX|INDICE DE FLUIDEZ|IND\. FLUIDEZ|\bIF\b)\s*[:=]?\s*(\d+(?:[.,]\d+)?)')
GPM_RE = re.compile(r'(\d+(?:[.,]\d+)?)\s*G\s*/\s*10\s*MIN')
DENSITY_RE = re.compile(r'DENSI(?:DAD|TY)\s*[:=]?\s*(0[.,]9\d{1,3})')

NOISE = re.compile(r'^(?:\d+KGS?|KGS?|\d+(?:[.,]\d+)?|PL\d+|B\d+KG|\d+MT|LOTE?|LOT|BATCH|CODE|NT|TM|HDPE|LDPE|LLDPE|PP|PET|PE|PEAD|PEBD|S/M|SM|N/A|ISO\d*|USO|BAGS?|USA)$')
GRADE_TOKEN = re.compile(r'(?<![A-Z0-9])([A-Z]{0,5}[ -]?\d[A-Z0-9]*(?:[-./][A-Z0-9]+)*|[A-Z]+\d[A-Z0-9]*(?:[-./][A-Z0-9]+)*)(?![A-Z0-9])')

def grade_key(value):
    return re.sub(r'[^A-Z0-9]', '', text(value))

@lru_cache(maxsize=1)
def catalog():
    if not CATALOG_PATH.exists(): return {}
    entries = json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
    out = {}
    for e in entries:
        for k in [e['grade'], *e.get('aliases', [])]: out[grade_key(k)] = e
    return out

# Palabras que llegan en el campo "marca" de DESC_COMER pero no son marca (polímero, genéricos).
NOT_BRAND = re.compile(r'^(?:HDPE|LDPE|LLDPE|PP|PE|PET|PEAD|PEBD|POLIETILENO|POLIPROPILENO|RESINA|RESINAS|SIN MARCA|GENERICO|VARIOS|NINGUNA|LTD|SM|INDUSTRIAL)\b')

def _value(v):
    v = text(v)
    return None if not v or v in MISSING else v

def _clean_grade(g):
    g = text(g).strip(' ,.;:-/')
    g = re.sub(r'\s+(?:PL\d+|B\d+KG|OB\d+ ?KG|\d+ ?KGS?|\d+MT|NT \d+)$', '', g)
    g = re.sub(r'^(?:GRADO|GRADE|CODIGO|COD|MODELO|MODEL)[:.\s]+', '', g)
    return g.strip(' ,.;:-/') or None

def _looks_grade(g):
    if not g or len(g) < 3 or len(g) > 18 or not re.search(r'\d', g) or not re.search(r'[A-Z]', g): return False
    if NOISE.match(g) or re.fullmatch(r'\d{6,}', g.replace('-', '')): return False
    return True

def _brand_in(t):
    m = BRAND_RE.search(t)
    return (BRANDS[m.group(1)], m) if m else (None, None)

def _grade_after(t, m):
    """Grado a continuación de una marca o nombre comercial: 'CERTENE HI-864U', 'MOPLEN EP300M B'."""
    rest = t[m.end():m.end() + 40]
    rest = re.sub(r'^(?:\s*(?:TM|®|\(R\)|PP|PE|HDPE|LDPE|LLDPE|POLYETHYLENE RESIN|POLYPROPYLENE)\b)+', '', rest).strip(' ,:-')
    tok = re.match(r'([A-Z]{0,4}[ -]?\d[A-Z0-9]*(?:[-./][A-Z0-9]+)*|[A-Z]+[ -]?\d[A-Z0-9]*(?:[-./][A-Z0-9]+)*)', rest)
    if tok:
        g = _clean_grade(tok.group(1))
        if _looks_grade(g): return g
    return None

POLY = r'(?:POLIPROPILENO|POLYPROPYLENE|POLIETILENO|POLYETHYLENE|HOMOPOLIMERO|COPOLIMERO|HOMOPOLYMER|COPOLYMER|RESINA PET|PET RESIN|HDPE|LDPE|LLDPE|PEAD|PEBD|PP|PET|PE)'
QUAL = r'(?:\s+(?:DE ALTA DENSIDAD|DE BAJA DENSIDAD|LINEAL|HOMOPOLIMERO|COPOLIMERO|HOMOPOLYMER|COPOLYMER|RANDOM|HETEROFASICO|IMPACTO|DE POLIPROPILENO|DE POLIETILENO|\((?:PP|HDPE|LDPE|LLDPE|PE|PET|PEAD)\)|RESIN|VIRGEN))*'
STOP_PREFIX = {'DE', 'EN', 'X', 'Y', 'A', 'CON', 'LA', 'EL', 'POR', 'SIN', 'LOS', 'LAS', 'AL', 'N', 'NO', 'S', 'C', 'U', 'TM', 'KG', 'O', 'E', 'MI', 'IF'}
TOKEN = r'((?:[A-Z]{1,3} )?[A-Z]{0,5}-?\d[A-Z0-9]*(?:[-./][A-Z0-9]+)*|[A-Z]+-?\d[A-Z0-9]*(?:[-./][A-Z0-9]+)*)'
AFTER_POLY = re.compile(r'(?<![A-Z])' + POLY + QUAL + r'\s+' + TOKEN + r'(?![A-Z0-9])')
BEFORE_POLY = re.compile(r'(?:^|\|)\s*' + TOKEN + r'\s+(?:-\s+)?(?:POLIETILENO|POLIPROPILENO|POLYETHYLENE|POLYPROPYLENE|LOW DENSITY|HIGH DENSITY|LINEAR LOW|HDPE|LDPE|LLDPE)')
ALONE = re.compile(r'(?:^|\|)\s*' + TOKEN + r'(?:\s+\d+MT)?\s*(?=\||$)')

def _generic_grade(t):
    for rx in (AFTER_POLY, BEFORE_POLY, ALONE):
        for m in rx.finditer(t):
            g = _clean_grade(m.group(1))
            if g and ' ' in g and g.split(' ')[0] in STOP_PREFIX: g = g.split(' ', 1)[1]
            if _looks_grade(g): return g
    return None

def extract(raw, description='', material=''):
    ma = (raw or {}).get('ma') or {}
    mbs = (raw or {}).get('mb_candidates') or []
    mb = mbs[0] if len(mbs) == 1 else {}
    evidence = []
    brand = grade = None
    full = text(description)

    # 1. DESC_COMER "nombre, marca, modelo"
    parts = [p.strip() for p in text(ma.get('DESC_COMER')).split(',')]
    if len(parts) >= 3:
        b, mdl = _value(parts[-2]), _value(parts[-1])
        if not mdl and len(parts) >= 4: b, mdl = _value(parts[-3]), _value(parts[-2])
        if mdl:
            kb, km = _brand_in(mdl)
            if km and _grade_after(mdl, km): brand, mdl = kb, _grade_after(mdl, km)
            elif re.search(r'\s', mdl) and not _looks_grade(_clean_grade(mdl)): mdl = None
        if b and not brand:
            known, _ = _brand_in(b)
            if known: brand = known
            elif _looks_grade(_clean_grade(b)) and not mdl: mdl = b
            elif not re.search(r'\d', b) and not NOT_BRAND.match(b): brand = b.title()
        if mdl and _looks_grade(_clean_grade(mdl)):
            grade = _clean_grade(mdl); evidence.append('Modelo declarado (DESC_COMER)')
    # 2. MB estructurado
    if not grade and _value(mb.get('MODE_MERCD')) and _looks_grade(_clean_grade(mb.get('MODE_MERCD'))):
        grade = _clean_grade(mb['MODE_MERCD']); evidence.append('Modelo declarado (MB)')
    if not brand and _value(mb.get('MARC_COMER')):
        mc = text(mb['MARC_COMER'])
        known, _ = _brand_in(mc); brand = known or (None if re.search(r'\d', mc) or NOT_BRAND.match(mc) else mc.title())
    # 3. Marca/nombre comercial seguido del grado en texto libre
    pool = ' | '.join(x for x in [text(mb.get('CARA_TIPO')), full] if x)
    for m in BRAND_RE.finditer(pool):
        g = _grade_after(pool, m)
        if g:
            if not grade: grade = g; evidence.append(f'Grado tras «{m.group(1)}»')
            if not brand or brand.upper() in ('S/M',) or brand == BRANDS.get(m.group(1)): brand = BRANDS[m.group(1)]
            break
    if not brand:
        known, _ = _brand_in(pool)
        brand = known
    # 4. Código / grado explícito
    if not grade:
        for m in re.finditer(r'(?:CODIGO|COD\.|GRADO|GRADE|MODELO)\s*[:.]?\s*' + TOKEN, pool):
            g = _clean_grade(m.group(1))
            if g and ' ' in g and g.split(' ')[0] in STOP_PREFIX: g = g.split(' ', 1)[1]
            if _looks_grade(g) and not re.fullmatch(r'[\d-]{6,}', g): grade = g; evidence.append('Código o grado declarado'); break
    # 5. Token tipo grado junto al nombre del polímero ("CP 360H", "TX7003 POLIETILENO")
    if not grade:
        g = _generic_grade(pool)
        if g: grade = g; evidence.append('Código junto al nombre del polímero')
    if grade and brand is None:
        kb, km = _brand_in(grade)
        if km: brand = kb; grade = _clean_grade(grade[km.end():]) or grade

    # Catálogo (sólo fichas verificadas aportan aplicación, MI y densidad)
    entry = catalog().get(grade_key(grade)) if grade else None
    if not entry and grade and ' ' in grade: entry = catalog().get(grade_key(grade.split(' ')[0]))
    if entry and entry.get('brand'):
        canonical, _ = _brand_in(text(entry['brand']))
        if brand is None or brand not in CANONICAL_BRANDS: brand = canonical or entry['brand']
    verified = entry if entry and entry.get('confidence') in ('alta', 'media') else None

    # Aplicación: la ficha técnica define la categoría del grado; el uso declarado se conserva aparte.
    declared_apps = [name for name, rx in APP_RES if rx.search(full)]
    if 'Película / film' in declared_apps and 'Soplado' in declared_apps and re.search(r'SOPLADO DE PELICULA|PELICULA SOPLADA|BLOWN FILM', full):
        declared_apps.remove('Soplado')
    if 'Extrusión' in declared_apps and len(declared_apps) > 1: declared_apps.remove('Extrusión')
    catalog_apps = list(verified.get('applications') or []) if verified else []
    if catalog_apps: primary, app_source = catalog_apps[0], 'ficha técnica'
    elif declared_apps: primary, app_source = declared_apps[0], 'declaración'
    else: primary, app_source = None, None
    # Con ficha verificada, la categoría la define la ficha; el uso declarado queda en grade_info (y marca discrepancia).
    applications = catalog_apps or declared_apps
    mismatch = bool(catalog_apps and declared_apps and not set(catalog_apps) & set(declared_apps))

    # Melt index y densidad: valor declarado en la serie, si no, ficha técnica
    mi = cond = mi_source = None
    m = MI_RE.search(full) or GPM_RE.search(full)
    if m:
        mi = Decimal(m.group(1).replace(',', '.')); mi_source = 'declaración'
    elif verified and verified.get('mi') is not None:
        mi = Decimal(str(verified['mi'])); cond = verified.get('mi_condition'); mi_source = 'ficha técnica'
    d = DENSITY_RE.search(full)
    density = Decimal(d.group(1).replace(',', '.')) if d else (Decimal(str(verified['density'])) if verified and verified.get('density') else None)

    polymer = verified.get('polymer') if verified else None
    values = dict(
        brand=brand, grade=grade, grade_key=grade_key(grade) if grade else None,
        application=primary, applications='|' + '|'.join(applications) + '|' if applications else None,
        melt_index=mi, density=density, product_name=None, grade_text=None,
        grade_info=dict(evidence=evidence, declared_applications=declared_apps, catalog_applications=catalog_apps,
                        application_source=app_source, application_mismatch=mismatch,
                        mi_source=mi_source, mi_condition=cond, polymer=polymer, iv=verified.get('iv') if verified else None,
                        catalog=bool(verified), source_url=verified.get('source_url') if verified else None,
                        catalog_name=verified.get('name') if verified else None, catalog_summary=verified.get('summary') if verified else None,
                        aliases=verified.get('aliases', []) if verified else [],
                        confidence=entry.get('confidence') if entry else None, version=GRADES_VERSION))
    return finish(values, material)

# Familia comercial del polímero: la ficha técnica manda; si no, la clasificación de la serie.
FAMILIES = ('HDPE', 'LDPE', 'LLDPE', 'PP', 'PET')
def family(polymer=None, material=None):
    p = text(polymer)
    if 'LLDPE' in p: return 'LLDPE'
    if p.startswith('PP'): return 'PP'
    if p in ('HDPE', 'LDPE', 'PET', 'EVA', 'POE'): return p
    return material if material in FAMILIES else None

APP_PHRASE = {'Soplado': 'moldeo por soplado', 'Inyección': 'moldeo por inyección', 'Película / film': 'película (film)',
              'Tubería': 'tubería', 'Rafia / monofilamento': 'rafia y monofilamento', 'Termoformado / lámina': 'termoformado y lámina',
              'Fibra / no tejido': 'fibra y no tejido', 'Rotomoldeo': 'rotomoldeo', 'Cables': 'cables', 'Recubrimiento': 'recubrimiento',
              'Tapas / compresión': 'tapas y moldeo por compresión', 'Extrusión': 'extrusión'}
DEFAULT_CONDITION = {'PP': '230 °C/2.16 kg', 'HDPE': '190 °C/2.16 kg', 'LDPE': '190 °C/2.16 kg', 'LLDPE': '190 °C/2.16 kg', 'EVA': '190 °C/2.16 kg'}
MI_SOURCE_LABEL = {'ficha técnica': 'ficha técnica', 'declaración': 'declarado en la DUA', 'correlación': 'inferido de otras DUA del mismo grado'}

def _num(v):
    return format(Decimal(v).normalize(), 'f') if v is not None else ''

def mi_hint(mi, fam, condition=None):
    """Lectura práctica del melt index: qué proceso sugiere la fluidez."""
    if mi is None or fam == 'PET': return None
    mi = float(mi)
    if condition and '21.6' in condition:
        return 'índice a carga alta (HLMI): resina de muy baja fluidez, típica de película de alta resistencia, tubería o soplado de piezas grandes'
    if fam == 'PP':
        for top, hint in ((2, 'fluidez baja: termoformado, lámina, tubería o soplado'), (5, 'fluidez media-baja: rafia, película o extrusión'),
                          (15, 'fluidez media: inyección general o película cast'), (40, 'fluidez alta: inyección de pared delgada y ciclos rápidos')):
            if mi < top: return hint
        return 'fluidez muy alta: fibras, no tejidos o inyección de pared muy delgada'
    for top, hint in ((0.5, 'fluidez muy baja: soplado, tubería o película de alta resistencia'), (2, 'fluidez baja: película soplada o extrusión'),
                      (5, 'fluidez media: rotomoldeo, tapas o inyección de piezas gruesas'), (20, 'fluidez alta: inyección general (cajas, baldes, tapas, envases)')):
        if mi < top: return hint
    return 'fluidez muy alta: inyección de pared delgada y ciclos rápidos'

def describe(fam, primary, applications, mi, condition, mi_source, density=None, iv=None):
    """Descripción corta con proceso y melt index identificable: 'HDPE para moldeo por inyección (no soplado). MI 8 g/10 min (...)'."""
    out = []
    if primary:
        contrast = ''
        if primary == 'Inyección' and 'Soplado' not in applications: contrast = ' (no soplado)'
        elif primary == 'Soplado' and 'Inyección' not in applications: contrast = ' (no inyección)'
        others = [APP_PHRASE[a] for a in applications if a != primary and a in APP_PHRASE][:2]
        out.append(f"{fam or 'Resina'} para {APP_PHRASE.get(primary, primary.lower())}{contrast}" + (f"; también {', '.join(others)}" if others else '') + '.')
    elif fam: out.append(f'{fam}; proceso no informado en la declaración ni en ficha técnica.')
    if mi is not None:
        cond = condition or DEFAULT_CONDITION.get(fam or '')
        hint = mi_hint(mi, fam, cond)
        out.append(f"MI {_num(mi)} g/10 min" + (f" ({cond})" if cond else '') + (f" — {hint}" if hint else '') + f" [{MI_SOURCE_LABEL.get(mi_source, mi_source)}].")
    elif iv: out.append(f'Viscosidad intrínseca {iv} dL/g.')
    elif fam != 'PET': out.append('MI no informado.')
    if density is not None: out.append(f'Densidad {_num(density)} g/cm³.')
    return ' '.join(out) or None

def full_name(fam, primary, brand, grade):
    """Nombre completo: 'HDPE INYECCIÓN CERTENE HI-864U'."""
    if not grade: return None
    b = re.sub(r'\s*\(.*?\)', '', brand or '').strip().upper()
    if b and (text(b) in text(grade) or 'DISTRIBUIDOR' in text(brand)): b = ''
    proc = primary.split(' /')[0].upper() if primary else ''
    return ' '.join(x for x in [fam, proc, b, grade] if x)

def finish(values, material=None, fam=None):
    """Campos derivados que dependen de la aplicación/MI finales (tras la correlación entre series del mismo grado)."""
    gi = values['grade_info']
    fam = family(gi.get('polymer')) or fam or family(None, material)
    apps = [a for a in (values['applications'] or '').split('|') if a]
    cond = gi.get('mi_condition') or (DEFAULT_CONDITION.get(fam or '') if values['melt_index'] is not None else None)
    summary = describe(fam, values['application'], apps, values['melt_index'], cond, gi.get('mi_source'), values['density'], gi.get('iv')) \
        if values['grade'] or values['application'] or values['melt_index'] is not None else None
    # La ficha verificada trae una lectura redactada; se usa si el MI vigente es el de la ficha.
    if gi.get('catalog_summary') and gi.get('mi_source') in ('ficha técnica', None): summary = gi['catalog_summary']
    gi.update(family=fam, mi_condition=cond, mi_hint=mi_hint(values['melt_index'], fam, cond), summary=summary)
    values['product_name'] = gi.get('catalog_name') or full_name(fam, values['application'], values['brand'], values['grade'])
    tags = [values['brand'] or '', values['grade'] or '', values['grade_key'] or '', *apps, gi.get('polymer') or '', fam or '',
            values['product_name'] or '', *gi.get('aliases', [])]
    values['grade_text'] = text(' '.join(t for t in tags if t)) or None
    return values

FIELDS = ('brand', 'grade', 'grade_key', 'application', 'applications', 'melt_index', 'density', 'product_name', 'grade_text', 'grade_info')

def _mode(items):
    from collections import Counter
    c = Counter(i for i in items if i is not None)
    return c.most_common(1)[0] if c else (None, 0)

def correlate(rows):
    """Patrones entre series del mismo grado: si una DUA declara el uso, el MI o la marca, las demás series del grado lo heredan
    (marcado como 'correlación'). Nunca sobrescribe la ficha técnica ni lo declarado en la propia serie."""
    groups = {}
    for material, v in rows:
        if v['grade_key']: groups.setdefault(v['grade_key'], []).append((material, v))
    for members in groups.values():
        if len(members) < 2: continue
        declared = [v['grade_info']['declared_applications'][0] for _, v in members if v['grade_info']['declared_applications']]
        app, votes = _mode(declared)
        app = app if declared and votes / len(declared) >= 0.5 else None
        mis = sorted(v['melt_index'] for _, v in members if v['grade_info'].get('mi_source') == 'declaración')
        mi = mis[len(mis) // 2] if mis else None
        brand, _ = _mode(v['brand'] for _, v in members)
        fam, _ = _mode(family(None, m) for m, _ in members)
        dens = sorted(v['density'] for _, v in members if v['density'] is not None)
        for material, v in members:
            gi = v['grade_info']; touched = False
            if app and not v['application']:
                v['application'] = app; v['applications'] = f'|{app}|'; gi['application_source'] = 'correlación'
                gi['correlated_series'] = len(declared); touched = True
            if mi is not None and v['melt_index'] is None:
                v['melt_index'] = mi; gi['mi_source'] = 'correlación'; gi['mi_condition'] = None; touched = True
            if dens and v['density'] is None: v['density'] = dens[len(dens) // 2]; touched = True
            if brand and not v['brand']: v['brand'] = brand; touched = True
            if touched or (fam and not family(gi.get('polymer'), material)): finish(v, material, fam)
    return rows

def apply(session, only_missing=False):
    """Recalcula marca/grado/aplicación/MI y la correlación entre series del mismo grado. Idempotente; no toca la
    clasificación de material. La correlación necesita todo el universo, por eso siempre recalcula todas las series."""
    from sqlalchemy import select
    from radar.models import Operation
    catalog.cache_clear()
    ops = list(session.scalars(select(Operation)))
    rows = correlate([(op.material, extract(op.raw, op.description, op.material)) for op in ops])
    changed = 0
    for op, (_, values) in zip(ops, rows):
        if any(getattr(op, k) != v for k, v in values.items()):
            for k, v in values.items(): setattr(op, k, v)
            changed += 1
    session.commit()
    return {'grades_updated': changed}

# Búsqueda de productos en lenguaje natural: "hdpe inyeccion", "pp rafia mi 3", "certene soplado".
FAMILY_TERMS = [('LLDPE', r'\bLLDPE\b|\bPEBDL\b|\bPELBD\b|\bMLLDPE\b|\bLINEAL\b|LINEAR LOW'), ('HDPE', r'\bHDPE\b|\bPEAD\b|ALTA DENSIDAD|HIGH DENSITY'),
                ('LDPE', r'\bLDPE\b|\bPEBD\b|BAJA DENSIDAD|LOW DENSITY'), ('PP', r'\bPP\b|POLIPROPILENO|POLYPROPYLENE|\bPROPILENO\b'),
                ('PET', r'\bPET\b|TEREFTALATO')]
APP_TERMS = [('Inyección', r'\bINY\w*|\bINJ\w*'), ('Soplado', r'\bSOPLAD\w*|\bBLOW MOLD\w*|\bBLOW\b|\bBOTELLAS?\b|\bFRASCOS?\b|\bBIDON\w*'), ('Película / film', r'\bPELICULA\w*|\bFILMS?\b|\bBOLSAS?\b'),
             ('Tubería', r'\bTUBERIA\w*|\bTUBOS?\b|\bPIPE\w*'), ('Rafia / monofilamento', r'\bRAFF?IA\b|\bMONOFILAMENTO\w*|\bCINTAS?\b'),
             ('Termoformado / lámina', r'\bTERMOFORM\w*|\bTHERMOFORM\w*|\bLAMINAS?\b'), ('Fibra / no tejido', r'\bFIBRAS?\b|NO TEJIDO|\bNONWOVEN\b'),
             ('Rotomoldeo', r'\bROTOMOLD\w*|\bROTOMOLDEO\b'), ('Cables', r'\bCABLES?\b'), ('Recubrimiento', r'\bRECUBRIM\w*|\bCOATING\b'),
             ('Tapas / compresión', r'\bTAPAS?\b|\bCOMPRESION\b'), ('Extrusión', r'\bEXTRUSION\b|\bEXTRUIDO\b')]
MI_QUERY = re.compile(r'\b(?:MI|MFI|MFR|IF|MELT INDEX|INDICE DE FLUIDEZ|FLUIDEZ)\s*(<=?|>=?|=)?\s*(\d+(?:\.\d+)?)(?:\s*(?:-|A)\s*(\d+(?:\.\d+)?))?')
FILLER = {'DE', 'PARA', 'EL', 'LA', 'LOS', 'LAS', 'POR', 'Y', 'CON', 'GRADO', 'MOLDEO', 'POLIETILENO', 'RESINA', 'USO', 'EN', 'G/10', 'MIN', 'G', '10'}

def parse_product_query(q):
    """Interpreta la búsqueda en filtros estructurados. El texto sobrante (marca, grado) se busca literal."""
    t = text(q).replace(',', '.')
    out = dict(family=None, application=None, mi_min=None, mi_max=None, terms=[])
    m = MI_QUERY.search(t)
    if m:
        op, a, b = m.group(1), Decimal(m.group(2)), m.group(3)
        if b: out['mi_min'], out['mi_max'] = a, Decimal(b)
        elif op and op.startswith('<'): out['mi_max'] = a
        elif op and op.startswith('>'): out['mi_min'] = a
        else: out['mi_min'], out['mi_max'] = (a * Decimal('0.85')).quantize(Decimal('0.001')), (a * Decimal('1.15')).quantize(Decimal('0.001'))
        t = t[:m.start()] + ' ' + t[m.end():]
    for name, rx in FAMILY_TERMS:
        if re.search(rx, t): out['family'] = name; t = re.sub(rx, ' ', t); break
    for name, rx in APP_TERMS:
        if re.search(rx, t): out['application'] = name; t = re.sub(rx, ' ', t); break
    t = re.sub(r'\b(?:POLIETILENO|POLYETHYLENE|PE)\b', ' ', t)
    out['terms'] = [w for w in re.findall(r'[A-Z0-9]+(?:[.\-/][A-Z0-9]+)*', t) if w not in FILLER]
    return out
