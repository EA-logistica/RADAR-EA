import hashlib
from pathlib import Path
from radar.sources import register_file
from radar.config import settings

def test_immutable_original_versions(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'raw_dir',tmp_path/'raw')
    source=tmp_path/'page.html';source.write_text('first')
    a=register_file(source,'query','http://example.test',{})
    source.write_text('second')
    b=register_file(source,'query','http://example.test',{})
    assert a['path']!=b['path']
    assert Path(a['path']).read_text()=='first'
    assert hashlib.sha256(Path(b['path']).read_bytes()).hexdigest()==b['id']
