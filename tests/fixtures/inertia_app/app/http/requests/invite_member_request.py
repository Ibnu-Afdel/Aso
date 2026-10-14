from pydantic import EmailStr

from fastogram.http import FormRequest


class InviteMemberRequest(FormRequest):
    error_bag = "invite"
    email: EmailStr
