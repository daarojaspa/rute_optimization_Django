"""The single (city, state) matching key shared by the data-build pipeline and the request path.

Interface: ``normalize_city_key(city, state) -> (city_key, state)`` (spec FR-001). Both
`stations/pipeline.py` and `routing/` import this one function (FR-002); a city that resolves
during the offline build can never fail to resolve here because of a second, divergent rule.
Pure and idempotent: normalizing an already-normalized pair returns it unchanged.
"""

# Closed list (FR-001). Whole-token match only, so "Stockton" never becomes "SAinockton".
_TOKEN_EXPANSIONS = {
    "ST.": "SAINT",
    "ST": "SAINT",
    "FT.": "FORT",
    "FT": "FORT",
    "MT.": "MOUNT",
    "MT": "MOUNT",
}


def normalize_city_key(city: str, state: str) -> tuple[str, str]:
    """Build the matching key: state trimmed/uppercased, city collapsed/uppercased/expanded."""
    normalized_state = state.strip().upper()
    collapsed = " ".join(city.split())
    city_key = " ".join(_TOKEN_EXPANSIONS.get(token, token) for token in collapsed.upper().split())
    return city_key, normalized_state
