"""Authentication and authorization (T-38, T-39, T-40).

```python
from aso.auth import auth, Gate, Authenticatable, MustVerifyEmail
from aso.auth.events import Registered, Login, Logout, Failed, Lockout

class User(MustVerifyEmail, Authenticatable, Model):
    ...

if await auth().attempt({"email": email, "password": password}):
    ...
```
"""

from __future__ import annotations

from aso.auth.authenticatable import Authenticatable, MustVerifyEmail
from aso.auth.features import features
from aso.auth.gate import Gate
from aso.auth.guard import auth
from aso.auth.password_broker import password_broker
from aso.exceptions.types import AuthenticationException, AuthorizationException

__all__ = [
    "Authenticatable",
    "AuthenticationException",
    "AuthorizationException",
    "Gate",
    "MustVerifyEmail",
    "auth",
    "features",
    "password_broker",
]
