import json
import pandas as pd
import pytest
from modules.gpexe_import import GPExeImportError, import_gpexe_file

def test_json_import(tmp_path):
    p=tmp_path/'g.json'; p.write_text(json.dumps({'records':[{'athlete':'A','metrics':{'Total Distance':1,'Maximum Speed':8},'units':{'Total Distance':'km','Maximum Speed':'m/s'}}]}))
    r=import_gpexe_file(p)
    assert r.rows_imported==1 and r.data.loc[0,'distance (m)']==1000 and r.data.loc[0,'max speed (km/h)']==28.8

def test_csv_partial_rejection(tmp_path):
    p=tmp_path/'g.csv'; pd.DataFrame([{'Total Distance':1000},{'Total Distance':'bad'}]).to_csv(p,index=False)
    r=import_gpexe_file(p)
    assert r.rows_imported==1 and r.rows_rejected==1

def test_invalid_fallback(tmp_path):
    p=tmp_path/'g.json'; p.write_text(json.dumps([{'Maximum Speed':30}]))
    with pytest.raises(GPExeImportError, match='fallback Excel'): import_gpexe_file(p)
