"""Copy legacy local database into UTF-8, keeping source and logical snapshot.
Stop API/worker first. Updates .env only after verifying every copied row.
"""
from pathlib import Path
from datetime import datetime
import json
import os
import sys
import psycopg
from psycopg import sql
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from alembic.config import Config
from alembic import command
from dotenv import dotenv_values, set_key

root=Path(__file__).resolve().parent.parent
os.chdir(root)
sys.path.insert(0,str(root))
from radar.db import Base
from radar import models

url=make_url(dotenv_values('.env')['DATABASE_URL'])
source=create_engine(url)
with source.connect() as c:
    encoding=c.scalar(text('SHOW server_encoding'))
    if encoding=='UTF8':
        print('Already UTF-8; no changes.');raise SystemExit(0)
    rows={t.name:[dict(r) for r in c.execute(select(t)).mappings()] for t in Base.metadata.sorted_tables}
counts={name:len(data) for name,data in rows.items()}
backup_dir=root/'data/backups';backup_dir.mkdir(parents=True,exist_ok=True)
backup=backup_dir/('pre-utf8-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
backup.write_text(json.dumps({'database':url.database,'encoding':encoding,'counts':counts,'tables':rows},ensure_ascii=True,default=str),encoding='utf-8')
target=url.database+'_utf8'
admin=url.set(drivername='postgresql',database='postgres').render_as_string(hide_password=False)
with psycopg.connect(admin,autocommit=True) as c:
    if c.execute('SELECT 1 FROM pg_database WHERE datname=%s',(target,)).fetchone():
        raise RuntimeError('Target exists; inspect before retrying: '+target)
    c.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C'").format(sql.Identifier(target)))
new_url=url.set(database=target)
destination=create_engine(new_url)
with destination.begin() as c:
    cfg=Config('alembic.ini');cfg.attributes['connection']=c
    command.upgrade(cfg,'head')
    for table in Base.metadata.sorted_tables:
        data=rows[table.name]
        for offset in range(0,len(data),500): c.execute(table.insert(),data[offset:offset+500])
        for col in table.primary_key.columns:
            seq=c.scalar(text('SELECT pg_get_serial_sequence(:table,:column)'),{'table':table.name,'column':col.name})
            if seq:
                maximum=max((r[col.name] for r in data),default=0)
                c.execute(text('SELECT setval(:seq,:value,:called)'),{'seq':seq,'value':maximum or 1,'called':bool(maximum)})
    for table in Base.metadata.sorted_tables:
        copied=[dict(r) for r in c.execute(select(table)).mappings()]
        pk=[col.name for col in table.primary_key.columns]
        order=lambda r:tuple(r[k] for k in pk)
        if sorted(copied,key=order)!=sorted(rows[table.name],key=order):
            raise RuntimeError('Copied data differs: '+table.name)
    assert c.scalar(text('SHOW server_encoding'))=='UTF8'
set_key('.env','DATABASE_URL',new_url.render_as_string(hide_password=False))
print('Verified UTF-8 database:',target,'; preserved rows:',counts,'; logical snapshot:',backup)
