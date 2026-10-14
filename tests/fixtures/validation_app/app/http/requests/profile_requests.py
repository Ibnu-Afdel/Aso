from typing import Annotated

from pydantic import EmailStr, Field

from fastogram.validation import Accepted, Confirmed, Exists, File, FormRequest, Image, Password, Unique
from fastogram.validation.uploaded_file import UploadedFile


class UpdateEmailRequest(FormRequest):
    """`Unique` with `ignore=`, exercised against the `users` table."""

    email: Annotated[EmailStr, Unique("users", ignore=lambda form: form.input("exclude_id"))]


class JoinTeamRequest(FormRequest):
    """`Exists`, exercised against the `teams` table."""

    team_id: Annotated[int, Exists("teams", "id")]


class ChangePasswordRequest(FormRequest):
    """`Confirmed` + the `Password` builder."""

    password: Annotated[str, Confirmed(), Password().min(8).letters().mixed_case().numbers().symbols()]
    password_confirmation: str


class AcceptTermsRequest(FormRequest):
    terms: Annotated[bool, Accepted()]


class UploadAvatarRequest(FormRequest):
    avatar: Annotated[UploadedFile, File(max_kb=50, mimes=["jpg", "png"])]


class UploadPhotoRequest(FormRequest):
    photo: Annotated[UploadedFile, Image(max_kb=50)]


class InviteMemberRequest(FormRequest):
    error_bag = "invite"
    email: EmailStr = Field(min_length=1)


class MixedUploadRequest(FormRequest):
    """Bracket-key arrays + an optional file, submitted as multipart `FormData`."""

    name: str
    tags: list[str] = Field(default_factory=list)
    avatar: Annotated[UploadedFile, File(max_kb=100, mimes=["jpg", "png"])] | None = None
