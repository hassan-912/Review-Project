"""Passport spread OCR regressions use invented text and geometry only."""
from copy import deepcopy
from io import BytesIO

from PIL import Image
import pytest

from tests.test_offline_spain_extraction import synthetic_mrz
from usa_passport_visual import visual_fields,verified_fields,read_fields
from usa_review import extract_fields,review_documents
from tests.test_usa_review import files,DS,CLIENT


def spread_rows():
    first,second=synthetic_mrz()
    data=[
        ('Type Country Code Passport No',.36,.53,.95,.55,.90),
        ('EGY',.49,.55,.55,.57,.99),('X00001234',.73,.55,.88,.57,.99),
        ('Full Nane',.37,.60,.48,.62,.79),
        ('ANNA',.37,.62,.47,.64,.99),('MARIATESTER',.50,.618,.87,.638,.99),
        ('Date Of Birth',.37,.65,.51,.67,.98),('01/01/1990',.37,.67,.51,.69,.99),
        ('Nationality',.37,.70,.49,.72,.99),('EGYPTIAN',.37,.72,.49,.74,.99),
        ('Sex',.52,.70,.57,.72,.99),('F',.52,.72,.54,.74,.99),
        ('Date of Issue',.37,.75,.51,.77,.99),('02/01/2020',.37,.77,.51,.79,.99),
        ('Date of Expiry',.52,.75,.67,.77,.99),('01/01/2031',.52,.77,.67,.79,.99),
        (first,.04,.90,.96,.92,.98),(second,.04,.94,.96,.96,.98)]
    return [dict(text=text,box=[x0,y0,x1,y1],confidence=confidence,page=1,method='local_ocr')
            for text,x0,y0,x1,y1,confidence in data]


def image_bytes():
    buffer=BytesIO();Image.new('RGB',(800,1100),'white').save(buffer,format='PNG')
    return buffer.getvalue()


def test_full_spread_combined_header_and_misread_name_label_are_supported():
    provisional=visual_fields(spread_rows(),'spread.png')
    assert provisional['passport_number']['value']=='X00001234'
    assert provisional['full_name']['value']=='ANNA MARIATESTER'
    fields=verified_fields(spread_rows(),'spread.png')
    expected={'full_name':'ANNA MARIA TESTER','surname':'TESTER','given_names':'ANNA MARIA',
              'passport_number':'X00001234','date_of_birth':'1990-01-01',
              'passport_issue':'2020-01-02','passport_expiry':'2031-01-01','nationality':'EGY','gender':'F'}
    for key,value in expected.items():
        assert fields[key]['status']=='extracted' and fields[key]['value']==value
        assert fields[key]['sources']


@pytest.mark.parametrize('change',['checksum','short_line','low_confidence','other_page','distant_zone'])
def test_invalid_or_ambiguous_machine_readings_remain_provisional(change):
    rows=spread_rows()
    if change=='checksum':rows[-1]['text']=rows[-1]['text'][:-1]+str((int(rows[-1]['text'][-1])+1)%10)
    elif change=='short_line':rows[-1]['text']=rows[-1]['text'][:-1]
    elif change=='low_confidence':rows[-1]['confidence']=.70
    elif change=='other_page':rows[-1]['page']=2
    else:rows[-2]['box'][1]=.5
    fields=verified_fields(rows,'spread.png')
    assert fields and all(f['status']=='needs_verification' for f in fields.values())


@pytest.mark.parametrize('key,index,value',[
    ('full_name',5,'SOMEONEELSE'),('passport_number',2,'X00001235'),
    ('date_of_birth',7,'01/01/1991'),('passport_expiry',15,'01/01/2030'),
    ('passport_issue',13,'02/01/2040'),('gender',11,'M'),('nationality',9,'BRITISH'),
])
def test_visual_and_machine_disagreement_is_never_overwritten(key,index,value):
    rows=spread_rows();rows[index]['text']=value
    fields=verified_fields(rows,'spread.png')
    assert fields[key]['status']=='needs_verification'
    assert value in fields[key]['value']


def test_detail_retry_uses_only_image_and_maps_evidence_to_original(monkeypatch):
    import offline_ocr
    original=spread_rows();original[-1]['confidence']=.7
    top=int((original[0]['box'][1]-.025)*1100)/1100
    retried=deepcopy(spread_rows())
    records=[]
    for row in retried:
        x0,y0,x1,y1=row['box']
        records.append(dict(text=row['text'],confidence=row['confidence'],
                            region_normalized=[x0,(y0-top)/(1-top),x1,(y1-top)/(1-top)]))
    calls=[]
    def ocr(raw):
        with Image.open(BytesIO(raw)) as image:calls.append(image.size)
        return records
    monkeypatch.setattr(offline_ocr,'image_lines',ocr)
    fields=read_fields(original,'spread.png',image_bytes())
    assert len(calls)==1 and calls[0][1]<2200
    assert fields['full_name']['value']=='ANNA MARIA TESTER' and fields['full_name']['status']=='extracted'
    source=next(s for s in fields['passport_number']['sources'] if s['method']=='verified_passport_mrz')
    assert source['box']==pytest.approx(spread_rows()[-1]['box'])
    assert source['page']==1 and source['source_file']=='spread.png'


def test_retry_failure_preserves_original_provisional_values(monkeypatch):
    import offline_ocr
    rows=spread_rows();rows[-1]['confidence']=.7
    monkeypatch.setattr(offline_ocr,'image_lines',lambda raw:(_ for _ in ()).throw(RuntimeError('OCR unavailable')))
    notes=[];fields=read_fields(rows,'spread.png',image_bytes(),notes)
    assert fields['passport_number']['value']=='X00001234'
    assert fields['passport_number']['status']=='needs_verification' and notes


def test_extraction_accepts_verified_spread_without_blanket_ocr_warning(monkeypatch):
    import offline_ocr
    monkeypatch.setattr(offline_ocr,'image_lines',lambda raw:[dict(r,region_normalized=r['box']) for r in spread_rows()])
    doc=extract_fields('passport','spread.png',image_bytes())
    assert not doc['limitations']
    assert doc['fields']['given_names']['value']=='ANNA MARIA'
    assert doc['fields']['passport_issue']['value']=='2020-01-02'
    assert all(s['source_file']=='spread.png' for f in doc['fields'].values() for s in f['sources'])


def test_missing_machine_zone_does_not_trigger_extra_ocr(monkeypatch):
    import offline_ocr
    monkeypatch.setattr(offline_ocr,'image_lines',lambda raw:pytest.fail('No unbounded OCR retries'))
    fields=read_fields(spread_rows()[:-2],'spread.png',image_bytes())
    assert fields['passport_number']['status']=='needs_verification'
