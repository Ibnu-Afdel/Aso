from aso.auth.events import Registered
from aso.events import Event
from aso.foundation import Application

from app.listeners.send_email_verification_notification import SendEmailVerificationNotification


def create_app():
    Event.listen(Registered, SendEmailVerificationNotification)

    return (
        Application.configure(base_path=__file__)
        .with_routing(web="routes/web.py", api="routes/api.py", health="/up")
        .create()
    )
