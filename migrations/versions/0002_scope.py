"""Separate catalog candidates from other imports without dropping original records."""
from alembic import op
import sqlalchemy as sa
revision='0002'
down_revision='0001'
def upgrade():
    op.add_column('operations',sa.Column('plastics_scope',sa.Boolean(),nullable=False,server_default=sa.true()))
    op.create_index('ix_operations_plastics_scope','operations',['plastics_scope'])
def downgrade():
    op.drop_index('ix_operations_plastics_scope',table_name='operations')
    op.drop_column('operations','plastics_scope')
