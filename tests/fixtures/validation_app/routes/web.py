from fastogram.routing import Route

from app.http.controllers.debug_controller import DebugController
from app.http.controllers.form_controller import FormController

Route.get("/forms/create", [FormController, "create"]).name("forms.create")
Route.post("/forms", [FormController, "store"]).name("forms.store")
Route.post("/forms/secure", [FormController, "secure"]).name("forms.secure")
Route.post("/forms/orders", [FormController, "order"]).name("forms.orders")
Route.post("/forms/invoices", [FormController, "invoice"]).name("forms.invoices")
Route.post("/forms/custom-messages", [FormController, "custom_messages"]).name("forms.custom_messages")
Route.post("/forms/email", [FormController, "update_email"]).name("forms.email")
Route.post("/forms/team", [FormController, "join_team"]).name("forms.team")
Route.post("/forms/password", [FormController, "change_password"]).name("forms.password")
Route.post("/forms/terms", [FormController, "accept_terms"]).name("forms.terms")
Route.post("/forms/avatar", [FormController, "upload_avatar"]).name("forms.avatar")
Route.post("/forms/photo", [FormController, "upload_photo"]).name("forms.photo")
Route.post("/forms/invite", [FormController, "invite_member"]).name("forms.invite")
Route.post("/forms/mixed", [FormController, "mixed_upload"]).name("forms.mixed")
Route.post("/forms/adhoc", [FormController, "adhoc"]).name("forms.adhoc")
Route.get("/forms/old", [FormController, "old_input"]).name("forms.old")
Route.get("/debug/session", [DebugController, "session_dump"]).name("debug.session")
