"""Creates a new user from validated registration data (T-38, Fortify's `CreateNewUser`).

Edit this to assign default roles, create workspace records, or set other defaults when a user
signs up. It survives framework/library upgrades because it lives in your own app code.
"""

from app.models.user import User


class CreateNewUser:
    async def create(self, data: dict) -> User:
        return await User.create(
            name=data["name"],
            email=data["email"].lower(),
            password=data["password"],
        )
