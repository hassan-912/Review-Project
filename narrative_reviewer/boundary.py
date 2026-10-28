"""Validate final wording at website boundaries, independently of the worker."""
from .contracts import Packet
from .grounding import validate_review
from .prose import prose_issues, ProseQualityError


def validate_final_review(packet, response):
    review = validate_review(packet, response)
    source_packet = packet.model_dump() if isinstance(packet, Packet) else packet
    issues = prose_issues(source_packet, review['findings'])
    if issues:
        raise ProseQualityError(issues)
    return review
