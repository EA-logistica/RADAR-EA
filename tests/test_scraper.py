import pytest
from radar.scraper import HEADERS, parse_html, SourceBlocked

def table(values):
    return '<p>1 a 1 de 1</p><table><tr>'+''.join('<th>'+h+'</th>' for h in HEADERS)+'</tr><tr>'+''.join('<td>'+x+'</td>' for x in values)+'</tr></table>'

def values():
    return ['118-26-484781','4-20100367395','28/09/2026','6243','4','999,000.00','1000','100','4133','VERDE','99000','990','1','3901200000','HDPE SHELL','HB5502B','','ENVASES','','24750','KG','0','US','24750','27,690.57','468.00','56.43','0','0','0','0','0','0','0','0']

def test_series_not_declaration_totals():
    rows,total=parse_html(table(values()))
    assert total==1
    assert str(rows[0]['fob_usd'])=='27690.57'
    assert str(rows[0]['net_kg'])=='24750'

def test_fail_closed():
    with pytest.raises(ValueError): parse_html('<html>Service unavailable</html>')
    with pytest.raises(SourceBlocked): parse_html('Ingrese el código que se muestra en la imagen')
    with pytest.raises(ValueError): parse_html(table(values()).replace('Fec. Numeración','Otra columna'))
    assert parse_html('No se encontraron registros')==([],0)
