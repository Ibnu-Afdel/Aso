from fastogram.http import Controller, redirect
from fastogram.inertia import inertia

from app.http.requests.invite_member_request import InviteMemberRequest
from app.http.requests.store_thing_request import StoreThingRequest


class ErrorsController(Controller):
    async def create(self):
        return inertia("errors/create", {})

    async def store(self, form: StoreThingRequest):
        return redirect().route("errors.create").with_flash("success", "Thing created.")

    async def invite(self, form: InviteMemberRequest):
        return redirect().route("errors.create")
