"""Bounded Gemini generation with one quota-only model fallback and no file store."""
import json
import httpx
from settings import setting
from gemini_usage import configured_models, provider_usage
from .contracts import Packet
from .model_output import DraftReview, gemini_schema
from .prompt import SYSTEM, request_context
from .sources import resolve_citations
from .boundary import validate_final_review


def review_gemini(packet,usage_sink,transport=None,before_model=None):
    packet=Packet.model_validate(packet).model_dump()
    key=setting('GEMINI_API_KEY')
    if not key:raise ValueError('gemini_config_missing')
    models=configured_models();attempted=[]
    context=request_context(packet)
    parts=[{'text':json.dumps(context,ensure_ascii=False,separators=(',',':'))}]
    for attachment in packet.get('attachments',[]):
        parts.extend([{'text':'Attached source document '+attachment['document_id']},
                      {'inlineData':{'mimeType':'application/pdf','data':attachment['data']}}])
    body=dict(systemInstruction={'parts':[{'text':SYSTEM}]},
              contents=[{'role':'user','parts':parts}],
              generationConfig={'responseFormat':{'text':{'mimeType':'APPLICATION_JSON','schema':gemini_schema()}},
                                'maxOutputTokens':8192,
                                'thinkingConfig':{'thinkingLevel':'LOW'}})
    try:
        with httpx.Client(timeout=httpx.Timeout(180,connect=15),trust_env=False,
                          follow_redirects=False,transport=transport) as client:
            for index,model in enumerate(models):
                if before_model:before_model(model,index)
                attempted.append(model)
                response=client.post('https://generativelanguage.googleapis.com/v1beta/models/'+model+':generateContent',
                                     headers={'x-goog-api-key':key},json=body)
                if len(response.content)>500000:raise ValueError('Gemini response exceeds the safe size')
                payload=response.json()
                # A rejection before generation can switch models once. Never
                # rerun a response with generated content or reported usage.
                if (response.status_code==429 and index+1<len(models) and
                        not payload.get('usageMetadata') and not payload.get('candidates')):
                    continue
                usage=provider_usage(payload.get('usageMetadata',{}))
                # Persist usage even if output validation or access later fails.
                usage_sink(usage)
                if response.status_code!=200:raise ValueError('Gemini request unavailable')
                break
    except (httpx.HTTPError,json.JSONDecodeError):
        # Do not propagate HTTP requests containing credentials into error telemetry.
        raise ValueError('Gemini request unavailable') from None
    candidates=payload.get('candidates') or []
    if len(candidates)!=1 or candidates[0].get('finishReason')!='STOP':
        raise ValueError('Gemini review did not finish')
    parts=candidates[0].get('content',{}).get('parts',[])
    text=''.join(p.get('text','') for p in parts if not p.get('thought'))
    draft=DraftReview.model_validate_json(text).model_dump()
    draft=resolve_citations(packet,draft)
    draft.update(version=packet['version'],request_id=packet['request_id'])
    review=validate_final_review(packet,draft)
    if len(draft['findings'])>=12:
        review['status']='incomplete'
        review['limitations'].append('The finding limit was reached; further manual review is required.')
    review.update(model=model,usage=usage,second_pass=False,models_attempted=attempted,fallback_used=len(attempted)>1)
    return review
