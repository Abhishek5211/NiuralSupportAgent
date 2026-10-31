from pydantic import BaseModel, Field

from .errors import APIError

EMPLOYER_ID = "emplr-4f2a91c8"


class AuthContext(BaseModel):
    """Mock auth: any nonempty token can access the supplied employer."""

    token: str = Field(default="", repr=False, exclude=True)
    employer_id: str = EMPLOYER_ID

    def authorize(self):
        if not self.token.strip():
            raise APIError(401, "An admin token is required.")
        if self.employer_id != EMPLOYER_ID:
            raise APIError(403, "Employer access denied.")
