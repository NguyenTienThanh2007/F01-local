class ApplicationError(Exception):
    """A safe domain/application error code; HTTP presentation lives in the API."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)
