"""Initial auditable import-series model."""
from alembic import op
from pathlib import Path

revision = "0001"
down_revision = None

def upgrade():
    for statement in Path(__file__).with_name('0001_schema.sql').read_text(encoding='utf-8').split(';'):
        if statement.strip(): op.execute(statement)

def downgrade():
    for table in ['reviews','revisions','alerts','operations','runs','artifacts']:
        op.drop_table(table)
