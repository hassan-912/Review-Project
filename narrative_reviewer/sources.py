"""Address source passages without asking a model to retype evidence."""
from copy import deepcopy
import re


def source_context(packet):
    context = deepcopy(packet)
    context.pop('attachments',None)
    sources = {}
    for document in context['documents']:
        for page in document['pages']:
            text = page.pop('text')
            passages = []
            # Keep each sentence verbatim. Bound long paragraphs by whitespace;
            # never summarize, change punctuation, or discard remaining text.
            for sentence in re.split(r'(?<=[.!?؟])\s+|\n+', text):
                remaining = sentence.strip()
                while remaining:
                    end = len(remaining)
                    if end > 1400:
                        end = remaining.rfind(' ', 0, 1400)
                        if end < 1:
                            end = 1400
                    quote = remaining[:end].strip()
                    remaining = remaining[end:].strip()
                    passage_id = f"{document['id']}:p{page['number']}:s{len(passages)+1}"
                    passages.append(dict(passage_id=passage_id, text=quote))
                    sources[passage_id] = dict(document_id=document['id'], page=page['number'], quote=quote)
            page['passages'] = passages
    return context, sources


def resolve_citations(packet, response):
    _, sources = source_context(packet)
    attached={a['document_id'] for a in packet.get('attachments',[])}
    def resolve(value):
        if isinstance(value,list):return [resolve(item) for item in value]
        if not isinstance(value,dict):return value
        if 'passage_id' in value:
            reference={k:v for k,v in value.items() if v is not None}
            passage_id=reference.get('passage_id')
            if passage_id:
                if set(reference)!={'passage_id'} or passage_id not in sources:
                    raise ValueError('Unknown source passage reference')
                return deepcopy(sources[passage_id])
            doc=next((d for d in packet['documents'] if d['id']==reference.get('document_id')),None)
            if (not doc or doc['id'] not in attached or set(reference)!={'document_id','page','quote'} or
                    not 1<=reference['page']<=doc['total_pages']):
                raise ValueError('Unknown visual source')
            return dict(**reference,visual=True)
        return {key:resolve(child) for key,child in value.items()}
    return resolve(deepcopy(response))
