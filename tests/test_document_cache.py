"""Reuse independent readings, while every changed file and every comparison stays fresh."""
from unittest.mock import Mock
import pytest

import document_cache
from document_cache import DocumentCache
from tests.test_local_review_pipeline import pdf


def test_changed_bytes_name_parser_or_version_are_not_cache_hits():
    cache=DocumentCache();reader=Mock(return_value={'values':{'number':'ONE'}})
    for parser,name,raw in [('parser','one.pdf',b'one'),('parser','one.pdf',b'one'),
                            ('parser','one.pdf',b'two'),('parser','two.pdf',b'two'),
                            ('other-parser','two.pdf',b'two')]:
        cache.read(parser,[(name,raw)],reader)
    assert reader.call_count==4 and cache.hits==1
    cache.version='new-parser-version'
    cache.read('other-parser',[('two.pdf',b'two')],reader)
    assert reader.call_count==5


def test_cached_values_do_not_share_mutable_evidence_between_reviews_or_browsers():
    reader=Mock(return_value={'fields':{'number':{'value':'ONE','sources':['source']}}})
    first=DocumentCache();second=DocumentCache()
    original=first.read('parser',[('file.pdf',b'bytes')],reader)
    original['fields']['number']['value']='MUTATED'
    returned=first.read('parser',[('file.pdf',b'bytes')],reader)
    assert returned['fields']['number']['value']=='ONE'
    returned['fields']['number']['sources'].append('invented')
    assert first.read('parser',[('file.pdf',b'bytes')],reader)['fields']['number']['sources']==['source']
    second.read('parser',[('file.pdf',b'bytes')],reader)
    assert reader.call_count==2


def test_cache_expires_evicts_and_does_not_keep_uploaded_bytes(monkeypatch):
    now=[1.0];monkeypatch.setattr(document_cache,'monotonic',lambda:now[0])
    cache=DocumentCache(max_entries=2,ttl=10);reader=Mock(return_value={'value':'parsed'})
    for number in range(3):cache.read('parser',[(str(number),b'PRIVATE RAW BYTES')],reader)
    assert len(cache.entries)==2 and 'PRIVATE RAW BYTES' not in repr(cache.entries)
    cache.read('parser',[('0',b'PRIVATE RAW BYTES')],reader)
    assert reader.call_count==4
    now[0]=20.0
    cache.read('parser',[('0',b'PRIVATE RAW BYTES')],reader)
    assert reader.call_count==5 and len(cache.entries)==1


def test_failed_extraction_is_retried_instead_of_cached():
    cache=DocumentCache();reader=Mock(side_effect=[ValueError('Synthetic'),{'value':'readable'}])
    with pytest.raises(ValueError):cache.read('parser',[('file',b'bytes')],reader)
    assert not cache.entries
    assert cache.read('parser',[('file',b'bytes')],reader)=={'value':'readable'}


def test_changing_one_application_reuses_other_parsers_but_compares_new_values(monkeypatch):
    import local_extraction
    from local_extraction import extract_local_documents
    from validator import _check_passport_number_crosscheck
    calls=[]
    def passport(raw,name):
        calls.append('passport')
        return dict(source_file=name,status='extracted',limitations=[],fields={
            'passport_number':dict(value='X00001234',status='extracted',sources=[])})
    def form(raw,category,name):
        calls.append('application')
        import pymupdf
        with pymupdf.open(stream=raw,filetype='pdf') as doc:
            value='X00001230' if 'CHANGED' in doc[0].get_text() else 'X00001234'
        return 'schengen_application',dict(source_file=name,status='extracted',limitations=[],fields=[
            dict(key='travel_document.number',value=value,normalized_value=value,status='extracted',page=1,sources=[])])
    monkeypatch.setattr(local_extraction,'extract_egypt_passport',passport)
    monkeypatch.setattr(local_extraction,'_form_report',form)
    cache=DocumentCache()
    files={'passport':[('passport.png',b'local image')],'visa_form':[('form.pdf',pdf('Original'))]}
    first=extract_local_documents(files,cache)
    assert _check_passport_number_crosscheck(first)==[]
    files['visa_form']=[('form.pdf',pdf('CHANGED'))]
    second=extract_local_documents(files,cache)
    issue,=_check_passport_number_crosscheck(second)
    assert calls==['passport','application','application']
    assert issue.found_value=='X00001230' and issue.expected_value=='X00001234'


def test_background_warmup_loads_models_once_without_reading_customer_documents(monkeypatch):
    from threading import current_thread
    import offline_ocr
    # conftest suppresses real warmup in UI tests; exercise the original helper here.
    original=_original_warmup
    original.cache_clear();threads=[]
    def english():
        threads.append(current_thread().name)
        return lambda image,**kwargs:(None,None)
    monkeypatch.setattr(offline_ocr,'_engine',english)
    monkeypatch.setattr(offline_ocr,'_arabic_engine',lambda:lambda image,**kwargs:None)
    first=original();second=original();first.join(timeout=2)
    assert first is second and not first.is_alive()
    assert threads==['local-ocr-startup']
    original.cache_clear()


# Capture before the autouse fixture replaces the helper for normal UI tests.
from offline_ocr import start_ocr_warmup as _original_warmup
