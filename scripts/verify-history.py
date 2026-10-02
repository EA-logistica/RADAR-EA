"""Read-only smoke tests for historical metrics on a running Radar installation."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright,expect

out=Path('data/qa');out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':1080})
    errors=[];failed=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('response',lambda r:failed.append(f'{r.status} {r.url}') if '/api/' in r.url and r.status>=400 else None)
    page.goto('http://127.0.0.1:8000',wait_until='networkidle')
    page.get_by_role('button',name='Histórico y métricas',exact=True).click()
    expect(page.get_by_role('heading',name='Histórico de importaciones',exact=True)).to_be_visible()
    expect(page.get_by_text('Precio mediano',exact=True)).to_be_visible()
    expect(page.locator('.history-table tbody tr').first).to_be_visible()
    page.wait_for_load_state('networkidle')
    page.screenshot(path=str(out/'radar-history-desktop.png'),full_page=True)
    page.get_by_role('button',name='Mensual',exact=True).click()
    expect(page.get_by_role('button',name='Mensual',exact=True)).to_have_attribute('aria-pressed','true')
    page.wait_for_load_state('networkidle')
    page.get_by_label('Métrica del gráfico').select_option('usd_kg')
    with page.expect_response(lambda r:'/api/analytics?' in r.url and 'grain=day' in r.url) as daily:
        page.get_by_role('button',name='Diario',exact=True).click()
    expect(page.locator('.history-table tbody tr')).to_have_count(len(daily.value.json()['timeline']))
    assert page.locator('.history-table tbody tr').count()>10
    page.get_by_role('button',name='Semanal',exact=True).click()
    page.wait_for_load_state('networkidle')
    with page.expect_download() as dl: page.get_by_role('button',name='Exportar histórico',exact=True).click()
    dl.value.save_as(str(out/'history.csv'))
    assert 'backed_days' in (out/'history.csv').read_text(encoding='utf-8-sig')
    page.get_by_role('button',name='Últimas 4 semanas',exact=True).click()
    page.wait_for_load_state('networkidle')
    page.get_by_label('Modo de comparación').select_option('custom')
    expect(page.get_by_text('Completa ambas fechas para comparar.',exact=False)).to_be_visible()
    page.get_by_label('Inicio del período comparado').fill('2026-09-01')
    page.get_by_label('Fin del período comparado').fill('2026-09-05')
    expect(page.get_by_text('Los períodos se superponen',exact=False)).to_be_visible()
    expect(page.get_by_test_id('delta-fob_usd')).to_have_text('Sin comparación válida')
    page.get_by_label('Modo de comparación').select_option('previous')
    page.get_by_role('button',name='Todo el histórico',exact=True).click()
    page.wait_for_load_state('networkidle')
    page.locator('.history-view .company-link').first.click()
    expect(page.get_by_text('Historial de compras',exact=True)).to_be_visible()
    page.get_by_role('button',name='Histórico y métricas',exact=True).click()
    page.wait_for_load_state('networkidle')
    if page.get_by_role('button',name='Cerrar aviso').is_visible(): page.get_by_role('button',name='Cerrar aviso').click()
    page.set_viewport_size({'width':390,'height':844})
    expect(page.get_by_role('heading',name='Histórico y métricas',exact=True)).to_be_visible()
    expect(page.get_by_role('heading',name='Histórico de importaciones',exact=True)).to_be_visible()
    expect(page.locator('.history-view')).not_to_have_class('history-view refreshing')
    expect(page.locator('.history-table tbody tr').first).to_be_attached()
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Horizontal overflow'
    page.screenshot(path=str(out/'radar-history-mobile.png'),full_page=True)
    assert not errors,errors
    assert not failed,failed
    (out/'history-ui-results.json').write_text(json.dumps({'status':'passed','console_errors':errors,'api_errors':failed,'checks':['day week month','price chart','history CSV','date presets','custom overlap suppression','company profile','responsive 390px']},indent=2),encoding='utf-8')
    browser.close()
    print('Historical UI tests passed')
