import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BoundsQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    north: float = Field(ge=-90, le=90)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    west: float = Field(ge=-180, le=180)

    @model_validator(mode="after")
    def check_order(self) -> "BoundsQuery":
        if self.south > self.north:
            raise ValueError("south must be less than or equal to north")
        if self.west > self.east:
            raise ValueError("west must be less than or equal to east")
        return self


class LocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cpso_number: str
    full_name: str
    specialties: Optional[str] = None
    gender: Optional[str] = None
    medical_school: Optional[str] = None
    languages_spoken: Optional[str] = None
    graduate_data: Optional[str] = None
    full_address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    latitude: float
    longitude: float
