"""Marca, grado, aplicación y melt index detectados por serie (capa derivada, recalculable)."""
from alembic import op
import sqlalchemy as sa
revision='0003'
down_revision='0002'
COLUMNS=[('brand',sa.Text()),('grade',sa.Text()),('grade_key',sa.String(40)),('application',sa.String(40)),('applications',sa.Text()),
         ('melt_index',sa.Numeric(12,4)),('density',sa.Numeric(8,4)),('product_name',sa.Text()),('grade_text',sa.Text()),('grade_info',sa.JSON())]
def upgrade():
    for name,kind in COLUMNS: op.add_column('operations',sa.Column(name,kind,nullable=True))
    op.create_index('ix_operations_grade_key','operations',['grade_key'])
    op.create_index('ix_operations_application','operations',['application'])
def downgrade():
    op.drop_index('ix_operations_application',table_name='operations')
    op.drop_index('ix_operations_grade_key',table_name='operations')
    for name,_ in reversed(COLUMNS): op.drop_column('operations',name)
