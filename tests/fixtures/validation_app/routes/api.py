from aso.routing import Route

from app.http.controllers.form_controller import FormController

Route.post("/forms", [FormController, "store"]).name("api.forms.store")
Route.post("/forms/email", [FormController, "update_email"]).name("api.forms.email")
