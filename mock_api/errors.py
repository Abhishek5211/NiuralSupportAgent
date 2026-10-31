class APIError(Exception):
    """An API failure with an HTTP-style status code."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code

    def as_dict(self):
        return {"error": {"status": self.status_code, "message": str(self)}}
