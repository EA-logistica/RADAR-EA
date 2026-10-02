from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED

root=Path(__file__).resolve().parent.parent
output=root/'radar-importaciones.zip'
roots=['radar','migrations','web','tests','scripts','docs']
excluded={'node_modules','__pycache__','dist','.pytest_cache'}
files=[p for directory in roots for p in (root/directory).rglob('*') if p.is_file() and not any(part in excluded for part in p.parts) and p.suffix!='.tsbuildinfo']
files += [root/name for name in ['README.md','pyproject.toml','requirements.lock','alembic.ini','compose.yaml','Dockerfile','.dockerignore','.gitignore','.env.example','package.json','package-lock.json']]
with ZipFile(output,'w',ZIP_DEFLATED) as z:
    for p in files:z.write(p,Path('radar-importaciones')/p.relative_to(root))
print(output)
