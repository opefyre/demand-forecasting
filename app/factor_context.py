"""Bounded declarations of market exposure, not inferred predictive effects."""
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator
from .commodity_prices import SERIES


class FactorContext(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    currency_exposure: StrictBool = False
    global_supply: StrictBool = False
    hormuz_route: StrictBool = False
    materials: list[str] = Field(default_factory=list, max_length=5)

    @model_validator(mode='after')
    def known_materials(self):
        if len(set(self.materials)) != len(self.materials) or set(self.materials)-set(SERIES):
            raise ValueError('Choose up to five distinct materials from the available list.')
        return self
