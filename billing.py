"""Token-based estimates from immutable rate/mode snapshots, never a provider invoice."""
from collections import defaultdict
from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo


def event_cost(event):
    """Unknown usage/rates stay unknown; cached input is not charged twice."""
    fields = ('input_tokens','output_tokens','input_usd_per_million',
              'cached_usd_per_million','output_usd_per_million')
    if any(event.get(key) is None for key in fields):
        return None
    incoming, outgoing = event['input_tokens'], event['output_tokens']
    cached = event.get('cached_input_tokens') or 0
    if incoming < 0 or outgoing < 0 or not 0 <= cached <= incoming:
        return None
    return ((Decimal(incoming-cached)*Decimal(str(event['input_usd_per_million']))
             + Decimal(cached)*Decimal(str(event['cached_usd_per_million']))
             + Decimal(outgoing)*Decimal(str(event['output_usd_per_million']))) / Decimal(1000000))


def summarize_costs(events):
    paid = Decimal(0)
    projected = Decimal(0)
    unknown = 0
    daily = defaultdict(lambda: {'paid':Decimal(0),'projected':Decimal(0)})
    models = defaultdict(lambda: {'requests':0,'paid':Decimal(0),'projected':Decimal(0),'unknown':0})
    reviews = defaultdict(lambda: {'requests':0,'paid':Decimal(0),'projected':Decimal(0),'unknown':0})
    details = []
    for event in events:
        cost = event_cost(event)
        day = datetime.fromisoformat(event['created_at'].replace('Z','+00:00')).astimezone(ZoneInfo('Africa/Cairo')).date().isoformat()
        model = models[event['model']]
        review = reviews[event.get('review_id') or 'unlinked']
        for group in (model,review):
            group['requests'] += 1
            group['unknown'] += cost is None or event.get('billing_mode') == 'unknown'
        if cost is None or event.get('billing_mode') == 'unknown':
            unknown += 1
        if cost is not None:
            projected += cost
            daily[day]['projected'] += cost
            for group in (model,review):
                group['projected'] += cost
        actual = Decimal(0) if event.get('billing_mode') == 'free' else cost if event.get('billing_mode') == 'paid' else None
        if actual is not None:
            paid += actual
            daily[day]['paid'] += actual
            for group in (model,review):
                group['paid'] += actual
        details.append(dict(event,projected_usd=float(cost) if cost is not None else None,
                            estimated_paid_usd=float(actual) if actual is not None else None))
    return dict(paid=paid,projected=projected,unknown=unknown,daily=dict(sorted(daily.items())),
                models=dict(models),reviews=dict(reviews),details=details,requests=len(events))
