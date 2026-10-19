from typing import Annotated

from fastapi import APIRouter, Query
from sqlmodel import select

from ..dependencies import SessionDep
from ..models import Doctor, DoctorAddress
from ..schemas.location import BoundsQuery, LocationRead

MAX_LOCATIONS = 1000

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("", response_model=list[LocationRead])
def read_locations(
    bounds: Annotated[BoundsQuery, Query()],
    session: SessionDep,
) -> list[LocationRead]:
    statement = (
        select(
            DoctorAddress.id,
            DoctorAddress.cpso_number,
            Doctor.full_name,
            Doctor.specialties,
            Doctor.gender,
            Doctor.medical_school,
            Doctor.languages_spoken,
            Doctor.graduate_data,
            DoctorAddress.full_address,
            DoctorAddress.city,
            DoctorAddress.province,
            DoctorAddress.postal_code,
            DoctorAddress.phone,
            DoctorAddress.fax,
            DoctorAddress.latitude,
            DoctorAddress.longitude,
        )
        .join(Doctor)
        .where(
            DoctorAddress.latitude >= bounds.south,
            DoctorAddress.latitude <= bounds.north,
            DoctorAddress.longitude >= bounds.west,
            DoctorAddress.longitude <= bounds.east,
        )
        .limit(MAX_LOCATIONS)
    )
    rows = session.exec(statement).all()
    return [LocationRead.model_validate(row) for row in rows]
