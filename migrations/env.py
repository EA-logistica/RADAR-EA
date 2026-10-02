from alembic import context
from radar.db import engine, Base
from radar import models

if context.is_offline_mode():
    context.configure(url=str(engine.url), target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction(): context.run_migrations()
else:
    connection_override=context.config.attributes.get('connection')
    if connection_override is not None:
        context.configure(connection=connection_override,target_metadata=Base.metadata)
        with context.begin_transaction(): context.run_migrations()
    else:
      with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction(): context.run_migrations()
