"""Named errors the API turns into controlled responses (never raw stack traces)."""


class ModelNotConfiguredError(Exception):
    """A model call is needed but the endpoint or key is missing."""


class IndexNotReadyError(Exception):
    """The chunk store is empty or the embeddings are missing."""


class ModelCallError(Exception):
    """A model call failed (network, quota, timeout); the message names the error type only."""
