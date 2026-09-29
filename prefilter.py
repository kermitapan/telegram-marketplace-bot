import re

# Common wish/request indicators in German and English.
_WISH_PATTERNS = re.compile(
    r'\b('
    r'suche[nt]?|suchen|suchе'
    r'|looking\s+for|lf\b|wtb\b'
    r'|brauche[n]?|benötige[n]?'
    r'|hätte\s+jemand|hat\s+jemand|hät\s+jemand'
    r'|anyone\s+have|does\s+anyone'
    r'|wanted\b|gesuch[t]?\b'
    r')\b',
    re.IGNORECASE,
)

# Already-taken indicators — post was edited to mark item as reserved/gone.
_TAKEN_PATTERNS = re.compile(
    r'\b('
    r'reserviert|reserviert\b|reserved'
    r'|vergeben|bereits\s+vergeben|schon\s+vergeben'
    r'|ist\s+weg|schon\s+weg|bereits\s+weg|weg\b'
    r'|vergeben\b|nicht\s+mehr\s+verfügbar'
    r')\b',
    re.IGNORECASE,
)

_GIVEAWAY_PATTERNS = re.compile(
    r'\b('
    r'verschenke[n]?|abzugeben|gratis|kostenlos|umsonst|zu\s+verschenken'
    r'|free\s+to\s+take|giving\s+away|for\s+free|take\s+it|take\s+away'
    r')\b',
    re.IGNORECASE,
)


def is_likely_wish(text: str) -> bool:
    """True if the text is almost certainly a wish/request — skip API call."""
    if not text:
        return False
    has_wish = bool(_WISH_PATTERNS.search(text))
    has_giveaway = bool(_GIVEAWAY_PATTERNS.search(text))
    return has_wish and not has_giveaway


def is_already_taken(text: str) -> bool:
    """True if the post has been marked as reserved or gone."""
    if not text:
        return False
    return bool(_TAKEN_PATTERNS.search(text))
