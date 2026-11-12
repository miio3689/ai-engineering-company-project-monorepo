"""Supplier directory models from the Milestone 09 Brasaland briefing."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .shared_paths import ensure_shared_python_path

ensure_shared_python_path()

from brasaland_shared.incidents import (  # noqa: E402
    Branch,
    Category,
    IncidentOrigin,
    IncidentStatus,
)


class SupplierStatus(str, Enum):
    active = "active"
    suspended = "suspended"


class Supplier(BaseModel):
    """Create/update payload; client-supplied IDs and timestamps are rejected."""

    model_config = ConfigDict(extra="forbid")

    name: str
    country: Literal["Colombia", "USA"]
    categories: list[
        Literal[
            "carne",
            "verduras_y_hortalizas",
            "salsas_y_condimentos",
            "bebidas",
            "packaging",
            "productos_limpieza",
            "lacteos",
            "carbon_y_combustible",
        ]
    ] = Field(min_length=1)
    rate_per_unit: float = Field(gt=0, allow_inf_nan=False)
    currency: Literal["COP", "USD"]
    status: SupplierStatus
    contact_email: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_country_currency(self) -> Supplier:
        expected_currency = "COP" if self.country == "Colombia" else "USD"
        if self.currency != expected_currency:
            raise ValueError(
                f"currency must be {expected_currency} when country is {self.country}"
            )
        return self


class SupplierResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    country: Literal["Colombia", "USA"]
    categories: list[
        Literal[
            "carne",
            "verduras_y_hortalizas",
            "salsas_y_condimentos",
            "bebidas",
            "packaging",
            "productos_limpieza",
            "lacteos",
            "carbon_y_combustible",
        ]
    ]
    rate_per_unit: float
    currency: Literal["COP", "USD"]
    status: SupplierStatus
    contact_email: str | None = None
    notes: str | None = None
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class IncidentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    by_origin: dict[str, int]
    by_branch: dict[str, int]


class IncidentBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    count: int
    percentage: float


class IncidentSatisfaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    average: float | None
    scored_cases: int
    counts: dict[str, int]


class IncidentAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_records: int
    valid_records: int
    invalid_records: int
    invalid_by_rule: dict[str, int]
    category_counts: dict[str, IncidentBreakdown]
    status_counts: dict[str, IncidentBreakdown]
    satisfaction: IncidentSatisfaction


class SupplierRateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rate_per_unit: float = Field(gt=0, allow_inf_nan=False)


class SupplierStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SupplierStatus


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    category: Category
    status: IncidentStatus
    origin: IncidentOrigin
    branch: Branch

    @field_validator("title", "description")
    @classmethod
    def require_nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Este campo es obligatorio.")
        return value


class Incident(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    title: str
    description: str
    category: Category
    status: IncidentStatus
    origin: IncidentOrigin
    branch: Branch
    created_at: datetime
    updated_at: datetime


class IncidentStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: IncidentStatus


class UserRole(str, Enum):
    admin = "admin"
    manager = "manager"
    user = "user"


class EmailModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, email: str) -> str:
        local, separator, domain = email.partition("@")
        local_pattern = r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
        label_pattern = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
        valid = (
            separator == "@"
            and len(email) <= 254
            and len(local) <= 64
            and bool(re.fullmatch(local_pattern, local))
            and not local.startswith(".")
            and not local.endswith(".")
            and ".." not in local
            and len(domain) <= 253
            and len(domain.split(".")) >= 2
            and all(re.fullmatch(label_pattern, label) for label in domain.split("."))
        )
        if not valid:
            raise ValueError("email must be a valid email address")
        return email


class ForgotPasswordRequest(EmailModel):
    pass


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str
    new_password: str


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: Literal["bearer"]


class MessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str


class UserCreate(EmailModel):
    password: str
    role: UserRole = UserRole.user


class UserRegistration(EmailModel):
    password: str
    name: str | None = None
    phone: str | None = None
    address: str | None = None


class RegistrationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str | None = None
    role: UserRole | None = None

    @field_validator("email")
    @classmethod
    def validate_optional_email(cls, email: str | None) -> str | None:
        if email is None:
            return email
        return EmailModel(email=email).email


class User(EmailModel):
    id: int
    hashed_password: str
    is_active: bool = True
    role: UserRole
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserResponse(EmailModel):
    id: int
    is_active: bool
    role: UserRole
    created_at: datetime


class ProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    phone: str | None = None
    address: str | None = None


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    phone: str | None = None
    address: str | None = None


class ProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    user_id: int
    name: str
    phone: str | None
    address: str | None


class AuthMeResponse(BaseModel):
    email: str
    role: UserRole
    profile: ProfileResponse | None
