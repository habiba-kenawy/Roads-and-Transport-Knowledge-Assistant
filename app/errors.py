"""Named errors the API turns into controlled responses (never raw stack traces)."""


class ModelNotConfiguredError(Exception):
    """A model call is needed but the endpoint or key is missing."""


class IndexNotReadyError(Exception):
    """The chunk store is empty or the embeddings are missing."""


class ModelCallError(Exception):
    """A model call failed (network, quota, timeout); the message names the error type only."""


class InvalidResumeError(Exception):
    """A resume for a thread with no pending clarification or the wrong interrupt id, or a new message to a thread that is waiting (HTTP 409)."""


class RequestTimeoutError(Exception):
    """The whole request took longer than REQUEST_TIMEOUT_SECONDS (HTTP 504); the run may still be finishing in the background."""


class ThreadBusyError(Exception):
    """A run is already in progress on this thread; the caller should retry when it finishes (HTTP 409)."""
