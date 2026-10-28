"""Text-only Gemini requests, source checks and durable usage. No real API calls."""
from copy import deepcopy
import json
from unittest.mock import Mock
import httpx
import pymupdf
import pytest
from streamlit.testing.v1 import AppTest
from extractor import VisaDocumentExtraction,SourceField
from narrative_reviewer.contracts import Packet,packet_digest
from narrative_reviewer.packet import build_packet
from narrative_reviewer.grounding import validate_review
from narrative_reviewer.client import review_gemini
from narrative_reviewer.sources import source_context


def pdf(*pages):
    doc=pymupdf.open()
    for text in pages:doc.new_page().insert_textbox(pymupdf.Rect(40,50,550,750),text,fontsize=11)
    raw=doc.tobytes();doc.close();return raw


@pytest.fixture
def packet():
    data=VisaDocumentExtraction(evidence_locations=[SourceField(document='visa_form',source_file='app.pdf',page=1,
        field_name='intended_arrival',value='2027-04-20',text='PRIVATE RAW REFERENCE',local_source=True)])
    return build_packet({'cover_letter':[('letter.pdf',pdf('My current trip arrival in Belgium is 21 April 2027.'))],
                         'visa_form':[('app.pdf',b'REFERENCE PDF MUST NEVER BE OPENED')]},data,ocr=False)


def review(packet,findings=True):
    return dict(version=packet['version'],request_id=packet['request_id'],status='complete',
        findings=[dict(section='cover_letter',kind='contradiction',title='Arrival dates differ',
            explanation='The letter and application give different dates for this trip.',
            suggestion='Confirm the correct arrival date and align the documents.',
            citations=[dict(document_id=d['id'],page=d['pages'][0]['number'],quote=d['pages'][0]['text'])
                       for d in packet['documents']])] if findings else [],
        coverage=[dict(document_id=d['id'],page=p['number'],status='reviewed')
                  for d in packet['documents'] for p in d['pages']],limitations=[])


def draft(packet):
    value=review(packet);value.pop('version');value.pop('request_id')
    for finding in value['findings']:finding['citations']=[{'passage_id':'d1:p1:s1'},{'passage_id':'d2:p1:s1'}]
    return value


def test_genuine_sources_are_retained_as_advisory_not_scored(packet):
    result=validate_review(packet,review(packet))
    assert result['status']=='complete' and len(result['findings'])==1
    assert result['scored'] is False


def test_invented_quote_is_rejected_without_a_clean_pass(packet):
    proposed=review(packet)
    proposed['findings'][0]['citations'][0]['quote']='This invented sentence is not present.'
    result=validate_review(packet,proposed)
    assert result['status']=='incomplete' and not result['findings']
    assert result['rejected_findings']==1


def test_wrong_page_and_unknown_document_cannot_be_cited(packet):
    for document,page in [('d1',99),('d99',1)]:
        proposed=review(packet)
        proposed['findings'][0]['citations'][0].update(document_id=document,page=page)
        assert not validate_review(packet,proposed)['findings']


def test_cross_customer_result_and_modified_packet_are_rejected(packet):
    proposed=review(packet);proposed['request_id']='a'*64
    with pytest.raises(ValueError):validate_review(packet,proposed)
    packet['documents'][0]['pages'][0]['text']='Someone else private letter.'
    with pytest.raises(ValueError):Packet.model_validate(packet)


def test_negations_and_numbers_are_not_normalized_away(packet):
    proposed=review(packet)
    proposed['findings'][0]['citations'][0]['quote']=packet['documents'][0]['pages'][0]['text'].replace('21','20')
    assert not validate_review(packet,proposed)['findings']


def test_a_contradiction_requires_two_different_quoted_passages(packet):
    proposed=review(packet)
    proposed['findings'][0]['citations']=proposed['findings'][0]['citations'][:1]
    assert validate_review(packet,proposed)['findings'][0]['kind']=='needs_verification'


def test_reference_only_finding_cannot_be_mislabelled_as_letter_problem(packet):
    proposed=review(packet)
    proposed['findings'][0]['citations']=proposed['findings'][0]['citations'][1:]
    assert not validate_review(packet,proposed)['findings']


def test_ocr_uncertainty_and_missing_coverage_block_complete_status(packet):
    packet['documents'][1]['pages'][0]['provisional']=True
    packet['request_id']=packet_digest(packet)
    result=validate_review(packet,review(packet))
    assert result['status']=='incomplete'
    assert result['findings'][0]['kind']=='needs_verification'
    proposed=review(packet);proposed['coverage']=[]
    assert validate_review(packet,proposed)['status']=='incomplete'


def test_duplicate_coverage_and_unexpected_schema_fields_are_rejected(packet):
    proposed=review(packet);proposed['coverage']*=2
    with pytest.raises(ValueError):validate_review(packet,proposed)
    proposed=review(packet);proposed['visa_approval_probability']=99
    with pytest.raises(ValueError):validate_review(packet,proposed)



@pytest.mark.parametrize('category',['passport','visa_form','hotel','flight','employment','insurance'])
def test_reference_bytes_and_raw_quotes_are_never_read_or_sent(monkeypatch,category):
    import narrative_reviewer.packet as module
    read=Mock(side_effect=AssertionError('Reference PDF was opened'))
    monkeypatch.setattr(module,'_read_pages',read)
    data=VisaDocumentExtraction(evidence_locations=[SourceField(document=category,source_file='ref.pdf',page=3,
        field_name='city',value='Paris',text='RAW PRIVATE ENTIRE PDF QUOTE',local_source=True)])
    value=build_packet({category:[('ref.pdf',b'RAW PDF BYTES')]},data)
    read.assert_not_called()
    text=json.dumps(value)
    assert 'RAW' not in text and 'Paris' in text
    assert value['documents'][0]['context_mode']=='extracted_fields'
    assert value['documents'][0]['pages'][0]['number']==3


def test_uncertain_local_fields_are_not_promoted_to_reference_facts():
    data=VisaDocumentExtraction(local_results=[dict(source_file='hotel.pdf',category='hotel',fields={
        'hotel_name':dict(status='needs_verification',value='Invented'),
        'city':dict(status='extracted',value='Paris',page=2)})])
    value=build_packet({'hotel':[('hotel.pdf',b'raw')]},data)
    assert 'Invented' not in json.dumps(value) and 'Paris' in json.dumps(value)


def test_missing_reference_facts_use_local_text_without_pdf_transfer():
    value=build_packet({'hotel':[('hotel.pdf',pdf('Secret hotel original PDF text.'))]})
    assert 'Secret hotel' in json.dumps(value) and not value['attachments']
    assert value['documents'][0]['context_mode']=='extracted_text'


def test_combined_letter_plan_is_deduplicated_and_references_stay_summarized():
    raw=pdf('My motivation letter and travel plan describe the current trip.')
    uploaded={'cover_letter':[('combined.pdf',raw)],'travel_plan':[('combined.pdf',raw)]}
    value=build_packet(uploaded,ocr=False)
    assert len(value['documents'])==1 and value['documents'][0]['categories']==['cover_letter','travel_plan']


def test_large_narrative_is_not_silently_omitted(monkeypatch):
    import narrative_reviewer.packet as module
    monkeypatch.setattr(module,'MAX_TOTAL_CHARS',15)
    with pytest.raises(ValueError,match='safe review size'):
        build_packet({'cover_letter':[('letter.pdf',pdf('Long letter that exceeds the limit of fifteen characters.'))]},ocr=False)


def response_payload(packet,**changes):
    value=dict(candidates=[dict(finishReason='STOP',content={'parts':[{'text':json.dumps(draft(packet))}]})],
               usageMetadata=dict(promptTokenCount=1000,candidatesTokenCount=100,thoughtsTokenCount=50,cachedContentTokenCount=200))
    value.update(changes);return value


def test_gemini_uses_only_text_and_tracks_all_chargeable_usage(monkeypatch,packet):
    import narrative_reviewer.client as module
    monkeypatch.setattr(module,'setting',lambda key:'test-key')
    observed=[];usage=[]
    def handler(request):
        observed.append(json.loads(request.content));assert request.headers['x-goog-api-key']=='test-key'
        assert '?' not in str(request.url)
        return httpx.Response(200,json=response_payload(packet))
    value=review_gemini(packet,usage.append,httpx.MockTransport(handler))
    assert value['findings'] and not value['scored'] and value['status']=='complete'
    sent=json.dumps(observed[0])
    assert 'PRIVATE RAW' not in sent and 'REFERENCE PDF' not in sent
    assert 'inlineData' not in sent and 'fileData' not in sent and 'tools' not in observed[0]
    assert usage[0]['billable_output_tokens']==150 and usage[0]['cached_input_tokens']==200


@pytest.mark.parametrize('failure',['truncated','invalid_json','bad_citation','http_error','blocked'])
def test_usage_is_recorded_even_when_review_is_rejected(monkeypatch,packet,failure):
    import narrative_reviewer.client as module
    monkeypatch.setattr(module,'setting',lambda key:'test-key')
    payload=response_payload(packet);status=200
    if failure=='truncated':payload['candidates'][0]['finishReason']='MAX_TOKENS'
    elif failure=='invalid_json':payload['candidates'][0]['content']['parts'][0]['text']='bad'
    elif failure=='bad_citation':
        value=draft(packet);value['findings'][0]['citations']=[{'passage_id':'d99:p1:s1'}]
        payload['candidates'][0]['content']['parts'][0]['text']=json.dumps(value)
    elif failure=='blocked':payload['candidates']=[]
    else:status=429
    calls=[];usage=[]
    def handler(request):calls.append(request);return httpx.Response(status,json=payload)
    with pytest.raises(ValueError):review_gemini(packet,usage.append,httpx.MockTransport(handler))
    assert len(calls)==1 and usage[0]['input_tokens']==1000


def test_transport_failure_has_no_retry_or_secret_in_error(monkeypatch,packet):
    import narrative_reviewer.client as module
    monkeypatch.setattr(module,'setting',lambda key:'test-key')
    calls=[]
    def handler(request):
        calls.append(request);raise httpx.ReadTimeout('private error test-key',request=request)
    with pytest.raises(ValueError) as error:review_gemini(packet,Mock(),httpx.MockTransport(handler))
    assert len(calls)==1 and 'test-key' not in str(error.value)


@pytest.mark.parametrize('lang',['en','ar'])
def test_report_has_no_manual_packet_or_colab_controls_and_no_rerun_api_call(monkeypatch,packet,lang):
    import narrative_reviewer.ui as module
    monkeypatch.setattr(module,'setting',lambda key:'fake')
    call=Mock(return_value=review(packet))
    ui=AppTest.from_string("""
import streamlit as st
from narrative_reviewer.ui import render_narrative_review
render_narrative_review(st.session_state.result,st.session_state.lang,lambda:None,st.session_state.runner)
""")
    packet['language']=lang;packet['request_id']=packet_digest(packet)
    ui.session_state.result=dict(narrative_requested=True,narrative_packet=packet,narrative_review=review(packet))
    ui.session_state.lang=lang;ui.session_state.runner=call
    ui.run();ui.run()
    assert not ui.exception and not ui.get('file_uploader') and not ui.get('download_button')
    call.assert_not_called()
    assert not any('Colab' in str(x.value) for x in ui.caption)


def test_reference_template_in_supporting_slot_still_never_sends_its_pdf(monkeypatch):
    import narrative_reviewer.packet as module
    monkeypatch.setattr(module,'_read_pages',Mock(side_effect=AssertionError('PDF was read')))
    data=VisaDocumentExtraction(local_results=[dict(category='visa_form',source_file='support.pdf',fields={
        'intended_arrival':dict(status='extracted',value='2027-04-20')})])
    packet=build_packet({'supporting':[('support.pdf',b'PRIVATE ORIGINAL PDF')]},data)
    assert packet['documents'][0]['context_mode']=='extracted_fields'
    assert 'PRIVATE ORIGINAL' not in json.dumps(packet)


def test_provider_schema_omits_unsupported_keywords_but_local_validation_keeps_limits():
    from narrative_reviewer.model_output import DraftReview,gemini_schema
    from pydantic import ValidationError
    raw=json.dumps(DraftReview.model_json_schema())
    sent=json.dumps(gemini_schema())
    for keyword in ('minLength','maxLength','pattern'):
        assert keyword in raw and keyword not in sent
    assert 'required' in sent and 'enum' in sent and 'maxItems' in sent


def test_pdf_fallback_is_allowed_for_scanned_supporting_only_and_remains_unverified(monkeypatch):
    import base64
    import narrative_reviewer.packet as module
    monkeypatch.setattr(module,'_bilingual_lines',lambda raw:[])
    raw=pdf('')
    packet=build_packet({'supporting':[('scan.pdf',raw)]},ocr=False)
    assert len(packet['attachments'])==1
    assert base64.b64decode(packet['attachments'][0]['data'])==raw
    assert 'data' not in source_context(packet)[0]
    value=dict(status='complete',findings=[dict(section='supporting',kind='translation_error',action='correct',
        title='Translation needs checking',explanation='The translated relationship needs verification.',
        suggestion='Verify the relationship against the Arabic original.',
        citations=[dict(passage_id=None,document_id='d1',page=1,quote='The translated relationship is mother.')])],
        coverage=[dict(document_id='d1',page=1,status='reviewed')],limitations=[])
    from narrative_reviewer.sources import resolve_citations
    value=resolve_citations(packet,value);value.update(version=packet['version'],request_id=packet['request_id'])
    result=validate_review(packet,value)
    assert result['status']=='incomplete' and result['findings'][0]['kind']=='needs_verification'
    assert result['findings'][0]['citations'][0]['visual']
    # The same mechanism is forbidden for a passport, even if someone alters its packet.
    packet['documents'][0]['categories']=['passport'];packet['request_id']=packet_digest(packet)
    with pytest.raises(ValueError):Packet.model_validate(packet)


def test_translation_error_requires_both_arabic_original_and_english_evidence():
    from document_ingestion import normalize_uploads
    raw='<html><body><p>الأصل العربي: العلاقة أب لمقدم الطلب.</p><p>English translation: Mother of the applicant.</p></body></html>'.encode()
    uploaded,converted=normalize_uploads({'supporting':[('family.html',raw)]})
    packet=build_packet(uploaded,ocr=False,converted_sources=converted)
    sources=list(source_context(packet)[1].values())
    value=dict(version=packet['version'],request_id=packet['request_id'],status='complete',findings=[dict(
        section='supporting',kind='translation_error',action='correct',title='Relationship mistranslated',
        explanation='The Arabic original says father while the English translation says mother.',
        suggestion='Correct the relationship in the English translation.',citations=sources)],
        coverage=[dict(document_id='d1',page=1,status='reviewed')],limitations=[])
    assert validate_review(packet,value)['findings'][0]['kind']=='translation_error'
    value['findings'][0]['citations']=[sources[-1]]
    assert validate_review(packet,value)['findings'][0]['kind']=='needs_verification'


def test_english_family_translation_without_arabic_original_is_incomplete():
    value=build_packet({'supporting':[('family.pdf',pdf('English translation of the family registry. Father of applicant.'))]},ocr=False)
    assert any('Arabic original' in note for note in value['limitations'])
