import os
import uuid
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from radar.db import Base
from radar import models

@pytest.fixture
def db():
    """Real PostgreSQL, separate disposable schema. Never truncate application tables."""
    url=os.getenv('TEST_DATABASE_URL')
    if not url: pytest.skip('TEST_DATABASE_URL is required for PostgreSQL integration tests')
    engine=create_engine(url)
    schema='radar_test_'+uuid.uuid4().hex
    with engine.begin() as c: c.execute(text(f'CREATE SCHEMA {schema}'))
    scoped=engine.execution_options(schema_translate_map={None:schema})
    Base.metadata.create_all(scoped)
    with sessionmaker(scoped,expire_on_commit=False)() as s:
        yield s
    with engine.begin() as c: c.execute(text(f'DROP SCHEMA {schema} CASCADE'))
    engine.dispose()

@pytest.fixture
def raw():
    return dict(CODI_ADUAN='118',ANO_PRESE='26',NUME_CORRE='123456',NUME_SERIE='1',FECH_INGSI='20260901',TIPO_DOCUM='4',LIBR_TRIBU='20100367395',DNOMBRE=' Empresa  plástica SAC ',PART_NANDI='3901200000',DESC_COMER='HDPE soplado MI 0.35',PESO_NETO='24750',UNID_FIQTY='24750',UNID_FIDES='KG',FOB_DOLPOL='27690.57',FLE_DOLAR='468',SEG_DOLAR='56.43',PAIS_ORIGE='US',FMOD='20260901')

@pytest.fixture
def artifact(tmp_path):
    p=tmp_path/'original.dbf';p.write_bytes(b'fixture raw bytes')
    import hashlib
    return dict(id=hashlib.sha256(p.read_bytes()).hexdigest(),source='test',url='https://example.test/source',period={'start':'2026-09-01','end':'2026-09-07'},path=str(p),bytes=p.stat().st_size,downloaded_at='2026-10-01T12:00:00+00:00')
