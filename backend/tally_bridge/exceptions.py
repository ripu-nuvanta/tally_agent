class TallyConnectionError(Exception):
    """Raised when TallyPrime is unreachable or times out."""
    pass


class TallyResponseError(Exception):
    """Raised when TallyPrime returns an unparseable or error response."""
    pass
