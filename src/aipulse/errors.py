class SourceFetchError(Exception):
    """Raised when a source's data can't be fetched or doesn't match its expected schema."""


class CommentaryError(Exception):
    """Raised when the commentary LLM call fails, returns invalid JSON, or fails
    schema/entity validation. Always caught by commentary.py -> template fallback."""
