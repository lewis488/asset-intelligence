from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Role = Literal["admin", "manager", "viewer"]
DatasetType = Literal["scanner", "cvi", "scrim", "reactive", "network", "vaisala", "vaisala_network"]


class AdminInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuthorityCreate(AdminInput):
    name: Name
    region: Name | None = None


class PatchInput(AdminInput):
    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        for field in self.model_fields_set - {"region"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class AuthorityPatch(PatchInput):
    name: Name | None = None
    region: Name | None = None


class AuthorityOut(BaseModel):
    id: int
    name: str
    region: str | None
    model_config = ConfigDict(from_attributes=True)


class UserCreate(AdminInput):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    authority_id: int = Field(gt=0)
    role: Role

    @model_validator(mode="after")
    def password_byte_limit(self):
        if len(self.password.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return self


class UserPatch(PatchInput):
    role: Role | None = None
    authority_id: int | None = Field(default=None, gt=0)
    is_active: bool | None = Field(default=None, strict=True)


class UserPasswordPatch(AdminInput):
    new_password: str = Field(min_length=8, max_length=72)

    @model_validator(mode="after")
    def password_byte_limit(self):
        if len(self.new_password.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return self


class DatasetOut(BaseModel):
    record_count: int
    last_upload_date: datetime | None


class AuthorityDataOut(BaseModel):
    authority_id: int
    authority_name: str
    datasets: dict[str, DatasetOut]


class DataOverviewOut(BaseModel):
    authorities: list[AuthorityDataOut]
    total_authorities: int


class UploadOut(BaseModel):
    dataset_type: DatasetType
    source_file: str | None
    upload_id: int | None = None
    record_count: int
    uploaded_at: datetime | None


class DatasetDelete(AdminInput):
    # An explicit null source_file selects legacy records without a filename.
    source_file: str | None = None
    upload_id: int | None = Field(default=None, gt=0)
