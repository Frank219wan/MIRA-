"""Small shared validation primitives for Week 1 contracts."""

from pydantic import BaseModel, ConfigDict


class ContractModel(BaseModel):
    """Reject unknown fields so model output cannot silently drift."""

    model_config = ConfigDict(extra="forbid")
