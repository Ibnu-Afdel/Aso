from pydantic import EmailStr

from aso.http import FormRequest


class InviteMemberRequest(FormRequest):
    error_bag = "invite"
    email: EmailStr
