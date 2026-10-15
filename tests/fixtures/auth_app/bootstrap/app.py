from fastogram.auth.events import Registered
from fastogram.events import Event
from fastogram.foundation import Application

from app.listeners.send_email_verification_notification import SendEmailVerificationNotification


def create_app():
    Event.listen(Registered, SendEmailVerificationNotification)

    return (
        Application.configure(base_path=__file__)
        .with_routing(web="routes/web.py", api="routes/api.py", health="/up")
        .create()
    )
