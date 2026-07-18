from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

INFRASTRUCTURE_TEST_SCHEMA_VERSION = 1
INFRASTRUCTURE_TEST_MESSAGE_MAX_LENGTH = 500
IDEMPOTENCY_KEY_MAX_LENGTH = 200
SAFE_ERROR_CODE_MAX_LENGTH = 100
SAFE_ERROR_MESSAGE_MAX_LENGTH = 1000


class InfrastructureTestArtifactContent(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: Literal["ok"]
    message: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=INFRASTRUCTURE_TEST_MESSAGE_MAX_LENGTH,
        ),
    ]

    def as_json(self) -> dict[str, object]:
        return {
            "status": self.status,
            "message": self.message,
        }
