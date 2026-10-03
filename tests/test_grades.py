from decimal import Decimal
from radar.grades import extract, parse_product_query, describe, mi_hint, full_name, correlate

CERTENE = ('POLIETILENO DE ALTA DENSIDAD, CERTENE, HI-864U | CERTENE HI-864U | EN SACOS DE 25 KGS | '
           'USO: PARA INYECCION DE ENVASES PLASTICOS | POLIETILENO DE ALTA DENSIDAD')

def test_brand_grade_and_full_name_from_declaration():
    r = extract({'ma': {'DESC_COMER': 'POLIETILENO DE ALTA DENSIDAD, CERTENE, HI-864U'}}, CERTENE, 'HDPE')
    assert (r['brand'], r['grade'], r['application']) == ('Certene (Muehlstein)', 'HI-864U', 'Inyección')
    assert r['product_name'] == 'HDPE INYECCIÓN CERTENE HI-864U'
    assert 'INYECCION' in r['grade_text'] and 'HDPE' in r['grade_text']

def test_declared_mi_is_described_with_condition_and_reading():
    r = extract({}, 'POLIETILENO DE ALTA DENSIDAD, S/M, S/M | PETROTHENE LH735-000 | DENSIDAD: 0.953 | INDICE DE FLUIDEZ: 0.33', 'HDPE')
    assert r['melt_index'] == Decimal('0.33') and r['density'] == Decimal('0.953')
    s = r['grade_info']['summary']
    assert 'MI 0.33 g/10 min (190 °C/2.16 kg)' in s and 'declarado en la DUA' in s

def test_describe_contrasts_injection_with_blow_molding():
    s = describe('HDPE', 'Inyección', ['Inyección'], Decimal('8'), '190 °C/2.16 kg', 'ficha técnica')
    assert s.startswith('HDPE para moldeo por inyección (no soplado).')
    assert 'MI 8 g/10 min (190 °C/2.16 kg)' in s and 'según' not in s and 'ficha técnica' in s

def test_mi_hint_depends_on_polymer():
    assert 'soplado' in mi_hint(Decimal('0.35'), 'HDPE')
    assert 'inyección general' in mi_hint(Decimal('8'), 'HDPE')
    assert 'rafia' in mi_hint(Decimal('3'), 'PP')
    assert mi_hint(Decimal('8'), 'PET') is None

def test_full_name_skips_distributor_and_repeated_brand():
    assert full_name('PP', 'Rafia / monofilamento', 'China Energy (Shenhua)', 'L5E89') == 'PP RAFIA CHINA ENERGY L5E89'
    assert full_name('HDPE', None, 'Snetor (distribuidor)', 'HD-5502') == 'HDPE HD-5502'

def test_parse_product_query():
    p = parse_product_query('hdpe inyeccion')
    assert (p['family'], p['application'], p['terms']) == ('HDPE', 'Inyección', [])
    p = parse_product_query('Polietileno de alta densidad para soplado MI 0,35')
    assert p['family'] == 'HDPE' and p['application'] == 'Soplado' and p['mi_min'] < Decimal('0.35') < p['mi_max']
    p = parse_product_query('pp mi>20')
    assert p['mi_min'] == Decimal('20') and p['mi_max'] is None
    assert parse_product_query('certene HI-864U')['terms'] == ['CERTENE', 'HI-864U']
    assert parse_product_query('lldpe film')['family'] == 'LLDPE'

def test_correlation_propagates_declared_use_and_mi_within_grade():
    a = extract({}, 'POLIETILENO, S/M, S/M | CERTENE HPB-9999 | PARA SOPLADO DE FRASCOS | MI 0.35', 'HDPE')
    b = extract({}, 'POLIETILENO, S/M, S/M | CERTENE HPB-9999 | 990 BAGS', 'HDPE')
    assert b['application'] is None and b['melt_index'] is None
    correlate([('HDPE', a), ('HDPE', b)])
    assert b['application'] == 'Soplado' and b['grade_info']['application_source'] == 'correlación'
    assert b['melt_index'] == Decimal('0.35') and 'inferido de otras DUA' in b['grade_info']['summary']
    assert a['grade_info']['application_source'] == 'declaración'
