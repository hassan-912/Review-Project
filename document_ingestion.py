"""Bounded, offline document conversion. Never runs Office macros, HTML or remote URLs."""
from datetime import datetime,timezone
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path,PurePath
import re
import struct
import zipfile
import xml.etree.ElementTree as ET

MAX_TEXT=400000
WORD_NS='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
TEXT_EXTENSIONS={'.docx','.doc','.html','.htm','.txt'}
UPLOAD_EXTENSIONS=['pdf','docx','doc','html','htm','txt','jpg','jpeg','png','webp','tif','tiff']


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','iframe','object','noscript'):self.hidden+=1
        if not self.hidden:
            if tag in ('p','div','tr','br','li','h1','h2','h3'):self.parts.append('\n')
            elif tag in ('td','th'):self.parts.append(' | ')
    def handle_endtag(self,tag):
        if tag in ('script','style','iframe','object','noscript'):self.hidden=max(0,self.hidden-1)
        if not self.hidden and tag in ('p','div','tr','li'):self.parts.append('\n')
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)


def _xml(raw):
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('upload_invalid')
    return ET.fromstring(raw)


def _decode(raw):
    declared=re.search(br'charset\s*=\s*["\x27]?([A-Za-z0-9_-]+)',raw[:4096],re.I)
    encoding=declared.group(1).decode('ascii') if declared else 'utf-8-sig'
    try:return raw.decode(encoding)
    except (UnicodeError,LookupError):
        from charset_normalizer import from_bytes
        match=from_bytes(raw).best()
        if match is None:raise ValueError('upload_invalid')
        return str(match)


def _docx(raw):
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        entries=archive.infolist()
        if (len(entries)>2000 or sum(e.file_size for e in entries)>50*1024**2 or
                len({e.filename for e in entries})!=len(entries) or
                any(e.flag_bits&1 or 'vbaproject' in e.filename.lower() for e in entries)):
            raise ValueError('upload_limit')
        names=archive.namelist()
        if 'word/document.xml' not in names:raise ValueError('upload_invalid')
        parts=[]
        def paragraph_text(paragraph):
            return ''.join(node.text or '' if node.tag==WORD_NS+'t' else '\t' if node.tag==WORD_NS+'tab'
                           else '\n' if node.tag==WORD_NS+'br' else '' for node in paragraph.iter())
        def blocks(node):
            if node.tag==WORD_NS+'p':
                value=paragraph_text(node)
                if value.strip():parts.append(value)
            elif node.tag==WORD_NS+'tbl':
                for row in node.findall(WORD_NS+'tr'):
                    parts.append(' | '.join(' '.join(paragraph_text(p) for p in cell.iter(WORD_NS+'p'))
                                            for cell in row.findall(WORD_NS+'tc')))
            else:
                for child in node:blocks(child)
        for name in ['word/document.xml']+sorted(n for n in names if re.fullmatch(r'word/(?:header|footer)\d+\.xml',n)):
            root=_xml(archive.read(name))
            blocks(root)
        # Image-only Word documents retain their embedded images for local OCR / PDF fallback.
        images=[archive.read(n) for n in names if n.startswith('word/media/') and
                PurePath(n).suffix.lower() in ('.png','.jpg','.jpeg','.tif','.tiff')]
        return '\n'.join(parts),images


def _doc_piece_text(word,table):
    """Word 97+ CLX piece table, per Microsoft's MS-DOC specification."""
    if len(word)<0x1AA:raise ValueError('word_conversion_failed')
    if struct.unpack_from('<H',word,10)[0]&0x100:raise ValueError('word_conversion_failed')
    offset,length=struct.unpack_from('<II',word,0x1A2)
    clx=table[offset:offset+length];position=0
    while position<len(clx) and clx[position]==1:
        if position+3>len(clx):raise ValueError('word_conversion_failed')
        position+=3+struct.unpack_from('<H',clx,position+1)[0]
    if position+5>len(clx) or clx[position]!=2:raise ValueError('word_conversion_failed')
    size=struct.unpack_from('<I',clx,position+1)[0];pieces=clx[position+5:position+5+size]
    if len(pieces)!=size or size<4 or (size-4)%12:raise ValueError('word_conversion_failed')
    count=(size-4)//12
    if count>100000:raise ValueError('upload_limit')
    cps=struct.unpack_from('<'+'I'*(count+1),pieces)
    if list(cps)!=sorted(cps) or cps[-1]>MAX_TEXT:raise ValueError('upload_limit')
    output=[]
    for index in range(count):
        fc=struct.unpack_from('<I',pieces,4*(count+1)+8*index+2)[0]
        compressed=bool(fc&0x40000000);start=fc&0x3fffffff
        if compressed:start//=2
        length=(cps[index+1]-cps[index])*(1 if compressed else 2)
        chunk=word[start:start+length]
        if len(chunk)!=length:raise ValueError('word_conversion_failed')
        output.append(chunk.decode('cp1252' if compressed else 'utf-16le',errors='strict'))
    return ''.join(output).replace('\r','\n').replace('\x07',' | ').replace('\x0b','\n').replace('\x0c','\n')


def native_text(name,raw):
    extension=PurePath(name).suffix.lower();images=[]
    if extension=='.docx':text,images=_docx(raw)
    elif extension=='.doc':
        if raw.lstrip().startswith((b'<',b'<!')):
            parser=_HTMLText();parser.feed(_decode(raw));text=''.join(parser.parts)
        else:
            import olefile
            with olefile.OleFileIO(BytesIO(raw)) as ole:
                word=ole.openstream('WordDocument').read()
                table=ole.openstream('1Table' if struct.unpack_from('<H',word,10)[0]&0x200 else '0Table').read()
                text=_doc_piece_text(word,table)
    elif extension in ('.html','.htm'):
        decoded=_decode(raw)
        if not re.search(r'<(?:!doctype|html|body|p|div|table|h[1-6])\b',decoded,re.I):raise ValueError('upload_invalid')
        parser=_HTMLText();parser.feed(decoded);text=''.join(parser.parts)
    elif extension=='.txt':text=_decode(raw)
    else:raise ValueError('upload_invalid')
    text=re.sub(r'[\x00-\x08\x0e-\x1f]','',text)
    text=re.sub(r'\n\s*\n+','\n\n',text).strip()
    if len(text)>MAX_TEXT:raise ValueError('upload_limit')
    if not text and not images:raise ValueError('word_conversion_failed')
    return text,images


def text_pdf(text,images=()):
    """A local reflowed evidence copy, with no external resources."""
    from fpdf import FPDF
    from fpdf.enums import XPos,YPos
    font=Path(__file__).parent/'assets/fonts'
    pdf=FPDF();pdf.set_creation_date(datetime(2000,1,1,tzinfo=timezone.utc))
    pdf.set_auto_page_break(True,15)
    pdf.add_font('Latin',fname=str(font/'NotoSans-Regular.ttf'))
    pdf.add_font('Arabic',fname=str(font/'NotoNaskhArabic-Regular.ttf'))
    pdf.set_fallback_fonts(['Arabic']);pdf.add_page();pdf.set_font('Latin',size=10)
    for line in text.splitlines():
        arabic=bool(re.search(r'[\u0600-\u06ff]',line))
        pdf.set_text_shaping(bool(arabic),direction='rtl' if arabic else None)
        pdf.set_font('Arabic' if arabic else 'Latin',size=10)
        pdf.multi_cell(0,5,line or ' ',new_x=XPos.LMARGIN,new_y=YPos.NEXT)
        if len(pdf.pages)>150:raise ValueError('upload_limit')
    for index,raw in enumerate(images):
        from PIL import Image
        with Image.open(BytesIO(raw)) as image:
            if image.width*image.height>25000000:raise ValueError('upload_limit')
        if text or index:pdf.add_page()
        pdf.image(BytesIO(raw),x=15,y=15,w=180,h=260,keep_aspect_ratio=True)
        if len(pdf.pages)>150:raise ValueError('upload_limit')
    return bytes(pdf.output())


def normalize_uploads(uploaded):
    """Keep original PDFs/images; convert text formats to bounded local PDF evidence."""
    result={};conversions={}
    for category,group in uploaded.items():
        for name,raw in group:
            if PurePath(name).suffix.lower() in TEXT_EXTENSIONS:
                text,images=native_text(name,raw)
                from hashlib import sha256
                converted=name+'.pdf';pdf=text_pdf(text,images)
                result.setdefault(category,[]).append((converted,pdf))
                conversions[sha256(pdf).hexdigest()]=dict(original_name=name,text=text,has_images=bool(images),reflowed=True)
            elif PurePath(name).suffix.lower() in ('.tif','.tiff'):
                from PIL import Image,ImageSequence
                frames=[]
                with Image.open(BytesIO(raw)) as image:
                    for frame in ImageSequence.Iterator(image):
                        if len(frames)>=150:raise ValueError('upload_limit')
                        buffer=BytesIO();frame.convert('RGB').save(buffer,format='PNG');frames.append(buffer.getvalue())
                result.setdefault(category,[]).append((name+'.pdf',text_pdf('',frames)))
            else:result.setdefault(category,[]).append((name,raw))
    return result,conversions
