from xml.sax.saxutils import escape
from zipfile import ZipFile
import pytest
from atgt.book2_package import read_manual_posts


def previous_book(path, values):
    """Minimal OOXML with nonstandard part name, as another Excel writer may emit."""
    cells = ''.join(f'<c r="{address}" t="inlineStr"><is><t>{escape(text)}</t></is></c>' for address,text in values.items())
    with ZipFile(path,'w') as z:
        z.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="THONG KE BIEN BAO ATGT" sheetId="7" r:id="signs"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="signs" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/signs.xml"/></Relationships>')
        z.writestr('xl/worksheets/signs.xml', f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row>{cells}</row></sheetData></worksheet>')


def test_manual_poles_resolve_sheet_name_and_keep_stable_cluster_ids(tmp_path):
    path=tmp_path/'previous.xlsx'
    previous_book(path, {'Q1':'ATGT_EXPORT_V1','R1':'P','Q8':'c2','O8':'User C2','Q10':'c1','O10':'User C1','Q11':'c1'})
    assert read_manual_posts(path,'P') == {'c1':'User C1','c2':'User C2'}


@pytest.mark.parametrize('changes,reason', [({'R1':'other'},'project'),({'O11':'different'},'Conflicting')])
def test_manual_pole_import_rejects_wrong_project_or_conflicting_values(tmp_path,changes,reason):
    path=tmp_path/'previous.xlsx'
    values={'Q1':'ATGT_EXPORT_V1','R1':'P','Q8':'c1','O8':'User C1','Q11':'c1'}
    previous_book(path,values | changes)
    with pytest.raises(ValueError, match=reason):read_manual_posts(path,'P')
