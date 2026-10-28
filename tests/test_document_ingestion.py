from io import BytesIO
from hashlib import sha256
import json
import struct
import zipfile
import pymupdf
import pytest
from PIL import Image
from document_ingestion import native_text,normalize_uploads,_doc_piece_text
from uploads import validate_uploads
from narrative_reviewer.packet import build_packet


def docx(xml):
    output=BytesIO()
    with zipfile.ZipFile(output,'w') as archive:
        archive.writestr('word/document.xml',xml)
    return output.getvalue()


def test_word_native_text_preserves_arabic_and_table_rows_without_pdf_roundtrip():
    raw=docx('''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
    <w:p><w:r><w:t>الأصل العربي الصحيح</w:t></w:r></w:p>
    <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Date</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Credit</w:t></w:r></w:p></w:tc></w:tr>
    <w:tr><w:tc><w:p><w:r><w:t>2026-01-01</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>20000 EGP</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
    </w:body></w:document>'''.encode())
    validate_uploads({'supporting':[('registry.docx',raw)]})
    text,_=native_text('registry.docx',raw)
    assert 'الأصل العربي الصحيح' in text and 'Date | Credit' in text and '2026-01-01 | 20000 EGP' in text
    uploads,converted=normalize_uploads({'supporting':[('registry.docx',raw)]})
    packet=build_packet(uploads,ocr=False,converted_sources=converted)
    assert 'الأصل العربي الصحيح' in packet['documents'][0]['pages'][0]['text']
    assert packet['documents'][0]['pages'][0]['method']=='native_text'
    assert not packet['attachments']


def test_html_does_not_execute_scripts_or_fetch_resources():
    raw=b'<html><body><p>Monthly salary EGP 20000</p><script>sendSecrets()</script><style>hidden</style><img src="https://example.invalid/private" /></body></html>'
    text,images=native_text('hr.html',raw)
    assert 'Monthly salary' in text and 'sendSecrets' not in text and not images
    normalized,converted=normalize_uploads({'employment':[('hr.html',raw)]})
    assert normalized['employment'][0][0]=='hr.html.pdf'
    with pymupdf.open(stream=normalized['employment'][0][1],filetype='pdf') as pdf:
        assert 'Monthly salary' in pdf[0].get_text()


@pytest.mark.parametrize('xml',[
    b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///secret">]><x>&x;</x>',
    b'<not-word />',
])
def test_invalid_or_entity_based_word_data_is_rejected(xml):
    with pytest.raises(ValueError):validate_uploads({'supporting':[('bad.docx',docx(xml))]})


def test_multipage_tiff_keeps_every_frame_without_blank_page():
    output=BytesIO();a=Image.new('RGB',(100,100),'white');b=Image.new('RGB',(100,100),'gray')
    a.save(output,format='TIFF',save_all=True,append_images=[b])
    uploads,_=normalize_uploads({'supporting':[('scan.tiff',output.getvalue())]})
    with pymupdf.open(stream=uploads['supporting'][0][1],filetype='pdf') as pdf:assert len(pdf)==2


@pytest.mark.parametrize('compressed',[True,False])
def test_legacy_word_piece_table_reads_text_without_launching_word(compressed):
    value='Salary 20000 EGP\r' if compressed else 'الراتب 20000 جنيه\r'
    word=bytearray(1200);offset=600
    encoded=value.encode('cp1252' if compressed else 'utf-16le');word[offset:offset+len(encoded)]=encoded
    piece=struct.pack('<II',0,len(value))+b'\x00\x00'+struct.pack('<I',(offset*2)|0x40000000 if compressed else offset)+b'\x00\x00'
    clx=b'\x02'+struct.pack('<I',len(piece))+piece
    struct.pack_into('<II',word,0x1A2,0,len(clx))
    assert _doc_piece_text(bytes(word),clx)==value.replace('\r','\n')
