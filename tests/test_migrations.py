import os
import uuid
import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine,text,inspect

def test_upgrade_downgrade_upgrade():
    url=os.getenv('TEST_DATABASE_URL')
    if not url: pytest.skip('TEST_DATABASE_URL required')
    e=create_engine(url);schema='radar_migration_test_'+uuid.uuid4().hex
    cfg=Config('alembic.ini')
    with e.begin() as c:
        c.execute(text(f'CREATE SCHEMA {schema}'))
        c.execute(text(f'SET search_path TO {schema}'))
        cfg.attributes['connection']=c
        command.upgrade(cfg,'head')
        assert 'plastics_scope' in {x['name'] for x in inspect(c).get_columns('operations')}
        command.downgrade(cfg,'base')
        assert 'operations' not in inspect(c).get_table_names()
        command.upgrade(cfg,'head')
        assert 'operations' in inspect(c).get_table_names()
        c.execute(text('SET search_path TO public'))
        c.execute(text(f'DROP SCHEMA {schema} CASCADE'))
    e.dispose()
