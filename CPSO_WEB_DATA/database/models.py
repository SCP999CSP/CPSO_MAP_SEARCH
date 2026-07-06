"""
CPSO 数据库表定义（SQLModel）
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Text
from sqlmodel import Field, Index, SQLModel


class Doctor(SQLModel, table=True):
    """医生表"""
    __tablename__ = "doctors"

    cpso_number: str = Field(primary_key=True, max_length=20)
    full_name: str
    registration_status: Optional[str] = None
    registration_status_label: Optional[str] = None
    gender: Optional[str] = None
    medical_school: Optional[str] = None
    languages_spoken: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    graduate_data: Optional[str] = None
    additional_address_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class DoctorAddress(SQLModel, table=True):
    """医生地址表（一个医生可有多个地址）"""
    __tablename__ = "doctor_addresses"
    __table_args__ = (
        Index("idx_doctor_addresses_cpso_number", "cpso_number"),
        Index("idx_doctor_addresses_city", "city"),
        Index("idx_doctor_addresses_postal_code", "postal_code"),
        Index("idx_doctor_addresses_is_primary", "is_primary"),
    )

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    cpso_number: str = Field(foreign_key="doctors.cpso_number", max_length=20)
    is_primary: bool = False
    not_in_practice: bool = False
    street1: Optional[str] = None
    street2: Optional[str] = None
    street3: Optional[str] = None
    street4: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    full_address: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geocode_status: Optional[str] = None
    geocoded_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
