from aso.http import Controller, Request, redirect
from aso.inertia import inertia
from aso.validation import validate
from aso.validation.form_request import old

from app.http.requests.order_request import StoreOrderRequest
from app.http.requests.profile_requests import (
    AcceptTermsRequest,
    ChangePasswordRequest,
    InviteMemberRequest,
    JoinTeamRequest,
    MixedUploadRequest,
    UpdateEmailRequest,
    UploadAvatarRequest,
    UploadPhotoRequest,
)
from app.http.requests.store_post_request import (
    CustomMessagesRequest,
    SecurePostRequest,
    StoreInvoiceRequest,
    StorePostRequest,
)


class FormController(Controller):
    async def create(self):
        return inertia("forms/create")

    async def store(self, form: StorePostRequest):
        return redirect().route("forms.create").with_flash("success", f"Created with slug {form.validated('slug')}.")

    async def secure(self, form: SecurePostRequest):
        return redirect().route("forms.create")

    async def order(self, form: StoreOrderRequest):
        return {"lines": form.validated("lines")}

    async def invoice(self, form: StoreInvoiceRequest):
        return redirect().route("forms.create")

    async def custom_messages(self, form: CustomMessagesRequest):
        return redirect().route("forms.create")

    async def update_email(self, form: UpdateEmailRequest):
        return {"email": form.validated("email")}

    async def join_team(self, form: JoinTeamRequest):
        return {"team_id": form.validated("team_id")}

    async def change_password(self, form: ChangePasswordRequest):
        return {"ok": True}

    async def accept_terms(self, form: AcceptTermsRequest):
        return {"ok": True}

    async def upload_avatar(self, form: UploadAvatarRequest):
        return {"size": form.validated("avatar").size}

    async def upload_photo(self, form: UploadPhotoRequest):
        return {"size": form.validated("photo").size}

    async def invite_member(self, form: InviteMemberRequest):
        return redirect().route("forms.create")

    async def mixed_upload(self, form: MixedUploadRequest):
        data = form.validated()
        avatar = data.get("avatar")
        return {"name": data["name"], "tags": data["tags"], "avatar_size": avatar.size if avatar else None}

    async def adhoc(self, request: Request):
        from pydantic import Field

        form = await validate(request, {"q": (str, Field(max_length=5))})
        return {"q": form.validated("q")}

    async def old_input(self):
        return {"title": old("title")}
