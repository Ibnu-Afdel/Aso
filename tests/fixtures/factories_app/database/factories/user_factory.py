from datetime import UTC, datetime

from aso.database import Factory

from app.models.user import User


class UserFactory(Factory):
    model = User

    def definition(self) -> dict:
        return {
            "name": self.faker.name(),
            "email": self.faker.unique.email(),
            "password": "password",
            "email_verified_at": datetime.now(UTC),
        }

    def unverified(self):
        return self.state({"email_verified_at": None})
