"""Validate visible Gemini advice without altering source quotations."""
import re
import unicodedata


class ProseQualityError(ValueError):
    def __init__(self, issues):
        super().__init__('Generated wording did not pass quality validation')
        self.issues = issues


def prose_issues(packet, findings):
    """Check visible prose; exact source quotes are deliberately excluded."""
    source = ' '.join(page['text'] for document in packet['documents'] for page in document['pages']).casefold()
    language = packet['language']
    issues = []
    for index, finding in enumerate(findings):
        for field in ('title', 'explanation', 'suggestion'):
            value = finding[field].strip()
            codes = []
            for word in re.findall(r'[^\W\d_]+', value, re.UNICODE):
                letters = [char for char in word if unicodedata.category(char).startswith('L')]
                script = 'LATIN' if language == 'en' else 'ARABIC'
                allowed={'LATIN','ARABIC'} if finding.get('kind')=='translation_error' else {script}
                if any(not any(name in unicodedata.name(char,'') for name in allowed) for char in letters) and word.casefold() not in source:
                    codes.append('unexpected_language')
                    break
            brackets = []
            for char in value:
                if char in '[({':
                    brackets.append(char)
                elif char in '])}':
                    if not brackets or brackets.pop() != {']':'[', ')':'(', '}':'{'}[char]:
                        codes.append('unbalanced_brackets')
                        break
            if brackets:
                codes.append('unbalanced_brackets')
            if field != 'title' and not re.search(r'''[.!?؟]["'”’\])}]*$''', value):
                codes.append('unfinished_sentence')
            for code in dict.fromkeys(codes):
                issues.append(dict(index=index, field=field, code=code))
    return issues

