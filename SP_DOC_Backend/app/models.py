"""
只读映射已有的 doctors / doctor_addresses 表，仅包含地图 API 用到的列。
表由 CPSO_SPDOC_DATA 创建和维护，本服务不建表、不改表。
"""
import uuid
from typing import Optional

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


class Doctor(SQLModel, table=True):
    __tablename__ = "doctors"

    cpso_number: str = Field(primary_key=True, max_length=20)
    full_name: str
    gender: Optional[str] = None
    medical_school: Optional[str] = None
    languages_spoken: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    graduate_data: Optional[str] = None
    specialties: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )


class DoctorAddress(SQLModel, table=True):
    __tablename__ = "doctor_addresses"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    cpso_number: str = Field(foreign_key="doctors.cpso_number", max_length=20)
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    full_address: Optional[str] = None
    phone: Optional[str] = None
    fax: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
