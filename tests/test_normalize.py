from decimal import Decimal
import pytest
from radar.normalize import classify, kilograms, price, normalize_ma, country, search_groups, entity
from radar.sources import archive_period

@pytest.mark.parametrize('hs,desc,material',[('3901200000','HDPE HIGH DENSITY POLYETHYLENE','HDPE'),('3901100000','LLDPE LINEAR LOW DENSITY POLYETHYLENE','LLDPE'),('3901100000','LDPE RESIN','LDPE'),('3902100000','PP INYECCION','PP'),('3907619000','PET BOTTLE GRADE','PET'),('3206190000','MASTERBATCH PP WHITE','Masterbatch'),('3812390000','ADITIVO ESTABILIZANTE','Aditivos')])
def test_classification(hs,desc,material): assert classify(hs,desc)[0]==material

def test_conflict_and_ambiguity():
    assert classify('3902100000','HDPE RESIN')[:2]==('Revisar',True)
    assert classify('3901100000','RESINA NATURAL')[:2]==('PE',True)
    assert classify('3901200000','HDPE / PP')[:2]==('Revisar',True)
    assert classify('3901300000','EVA RESIN')[0]=='Otros'
    assert classify('3907690000','PETG RESIN')[0]=='Otros'

def test_relevance_avoids_food_and_empty_packaging():
    from radar.normalize import relevant
    assert not relevant('2009690000','MOSTO CONCENTRADO TINTO COLOR 300')
    assert not relevant('8443990000','CARTUCHO ADITIVO VACIO PLASTICO')
    assert relevant('3206190000','MASTERBATCH WHITE')

@pytest.mark.parametrize('qty,unit,expected',[('24.75','TM',Decimal('24750')),('1000','G',Decimal('1')),('10','LB',Decimal('4.53592370')),('990','BOLSAS',None),('0','KG',None),('-1','KG',None),('1','TON',None)])
def test_mass(qty,unit,expected): assert kilograms(qty,unit)[0]==expected

def test_prices():
    assert price('27690.57','24750')==Decimal('27690.57')/Decimal('24750')
    assert price('1','0') is None
    assert price('1','1','PEN') is None
    assert price('1','1',same_series=False) is None
    assert price('NaN','1') is None
    assert price('-2','1') is None

def test_names_and_country():
    assert entity(' No Disponible ') is None
    assert country('USA')=='US'
    assert country('0') is None
    assert entity('  empresa   plástica S.A. ')=='EMPRESA PLASTICA S.A.'

def test_related_terms():
    g=search_groups('HDPE soplado MI 0,35')
    assert g[-1]==['0.35']
    assert 'BLOW MOLDING' in g[1]
    assert search_groups('HB5502B')==[['HB5502B']]

def test_week_across_month():
    assert archive_period('ma31060926.zip')['start']=='2026-08-31'
    with pytest.raises(ValueError): archive_period('ma99270926.zip')

def test_supplier_not_brand(raw):
    r=normalize_ma(raw,[dict(PART_NANDI='3901200000',NOMB_PROVE='No Disponible',VFOB_ITEM='27690.57',MARC_COMER='SHELL')])
    assert r['supplier'] is None and r['supplier_status']=='redacted'

def test_supplier_matching(raw):
    supplier=dict(PART_NANDI='3901200000',NOMB_PROVE='ACME',VFOB_ITEM='27690.57')
    assert normalize_ma(raw,[supplier])['supplier']=='ACME'
    assert normalize_ma(raw,[{**supplier,'VFOB_ITEM':'999'}])['supplier'] is None
    assert normalize_ma(raw,[supplier,supplier])['supplier'] is None

def test_cif_and_audit(raw):
    r=normalize_ma(raw)
    assert r['cif_usd']==Decimal('28215.00')
    assert r['raw']['ma']==raw
    assert r['net_kg']==Decimal('24750')
    assert r['importer_ruc']=='20100367395'
