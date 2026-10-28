"""Optional local OCR. Documents are never sent to a remote service."""
from functools import lru_cache
from io import BytesIO
from threading import RLock,Thread
import pymupdf

_OCR_LOCK=RLock()


@lru_cache(maxsize=1)
def _engine():
    from rapidocr_onnxruntime import RapidOCR
    return RapidOCR(intra_op_num_threads=2,inter_op_num_threads=1)


@lru_cache(maxsize=1)
def start_ocr_warmup():
    """Prime OCR using generated text while files are chosen; no customer documents read."""
    def prepare():
        try:
            import numpy as np
            from PIL import Image,ImageDraw,ImageFont
            image=Image.new('RGB',(1200,220),'white')
            draw=ImageDraw.Draw(image);font=ImageFont.load_default(size=32)
            draw.text((25,25),'Document reader ready',fill='black',font=font)
            draw.text((25,85),'01234567890123456789012345678901234567890123',fill='black',font=font)
            pixels=np.array(image)
            with _OCR_LOCK:
                _engine()(pixels,use_cls=False)
                _arabic_engine()(pixels,use_det=True,use_cls=False,use_rec=True)
        except Exception as exc:
            from monitoring import capture_error
            capture_error(exc,'ocr_startup')
    thread=Thread(target=prepare,name='local-ocr-startup',daemon=True)
    thread.start()
    return thread


def image_lines(raw):
    from PIL import Image
    import numpy as np
    image=Image.open(BytesIO(raw)).convert('RGB')
    # Shared CPU model instances are serialized across concurrent website reviews.
    with _OCR_LOCK:result,_=_engine()(np.array(image),use_cls=False)
    return [dict(text=text,confidence=float(score),region_normalized=[
        min(point[0] for point in box)/image.width,min(point[1] for point in box)/image.height,
        max(point[0] for point in box)/image.width,max(point[1] for point in box)/image.height],
        method='local_ocr') for box,text,score in result or []]


@lru_cache(maxsize=1)
def _arabic_engine():
    from rapidocr import RapidOCR,LangRec,OCRVersion,ModelType
    return RapidOCR(params={'Rec.lang_type':LangRec.ARABIC,'Rec.ocr_version':OCRVersion.PPOCRV5,
        'Rec.model_type':ModelType.MOBILE,'Det.ocr_version':OCRVersion.PPOCRV4,
        'Det.model_type':ModelType.MOBILE,'Global.use_cls':False,'Global.log_level':'warning',
        'EngineConfig.onnxruntime.intra_op_num_threads':2,'EngineConfig.onnxruntime.inter_op_num_threads':1})


def arabic_image_lines(raw):
    from PIL import Image
    import numpy as np
    image=Image.open(BytesIO(raw)).convert('RGB')
    with _OCR_LOCK:result=_arabic_engine()(np.array(image),use_det=True,use_cls=False,use_rec=True)
    if result.txts is None:return []
    return [dict(text=text,confidence=float(score),region_normalized=[
        float(min(point[0] for point in box)/image.width),float(min(point[1] for point in box)/image.height),
        float(max(point[0] for point in box)/image.width),float(max(point[1] for point in box)/image.height)],
        method='local_arabic_ocr') for box,text,score in zip(result.boxes,result.txts,result.scores)]


def arabic_image_line(raw):
    """Recognize one already located text line without splitting a printed ID into digits."""
    from PIL import Image
    import numpy as np
    image=Image.open(BytesIO(raw)).convert('RGB')
    with _OCR_LOCK:result=_arabic_engine()(np.array(image),use_det=False,use_cls=False,use_rec=True)
    return [dict(text=text,confidence=float(score),region_normalized=[0,0,1,1],
                 method='local_arabic_ocr') for text,score in zip(result.txts or [],result.scores or [])]


def pdf_lines(raw,pages=None):
    """Return page text/positions; render only pages without a usable text layer."""
    result=[]
    with pymupdf.open(stream=raw,filetype='pdf') as pdf:
        for number in pages or range(1,len(pdf)+1):
            if not 1<=number<=len(pdf):continue
            page=pdf[number-1]
            if len(page.get_text().strip())>=30:
                for block in page.get_text('dict')['blocks']:
                    for line in block.get('lines',[]):
                        text=''.join(span['text'] for span in line['spans']).strip()
                        if text:result.append(dict(text=text,page=number,confidence=None,method='pdf_text',
                            region_normalized=[line['bbox'][0]/page.rect.width,line['bbox'][1]/page.rect.height,
                                               line['bbox'][2]/page.rect.width,line['bbox'][3]/page.rect.height]))
            else:
                pix=page.get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False)
                result.extend(dict(line,page=number) for line in image_lines(pix.tobytes('png')))
    return result


def pdf_region_lines(raw,page_number,region):
    """A tight labelled region can keep a nearby CONTACT heading out of a name."""
    with pymupdf.open(stream=raw,filetype='pdf') as pdf:
        page=pdf[page_number-1]
        rect=pymupdf.Rect(region)
        native=page.get_text(clip=rect).strip()
        if native:
            return [dict(text=native,page=page_number,confidence=None,method='pdf_text',
                         region_normalized=[rect.x0/page.rect.width,rect.y0/page.rect.height,rect.x1/page.rect.width,rect.y1/page.rect.height])]
        pix=page.get_pixmap(matrix=pymupdf.Matrix(4,4),clip=rect,alpha=False)
        return [dict(line,page=page_number,region_normalized=[
            (rect.x0+line['region_normalized'][0]*rect.width)/page.rect.width,
            (rect.y0+line['region_normalized'][1]*rect.height)/page.rect.height,
            (rect.x0+line['region_normalized'][2]*rect.width)/page.rect.width,
            (rect.y0+line['region_normalized'][3]*rect.height)/page.rect.height])
            for line in image_lines(pix.tobytes('png'))]
