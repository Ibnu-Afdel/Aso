"""Authentication and authorization (T-38, T-39, T-40).

```python
from fastogram.auth import auth, Gate, Authenticatable, MustVerifyEmail
from fastogram.auth.events import Registered, Login, Logout, Failed, Lockout

class User(MustVerifyEmail, Authenticatable, Model):
    ...

if await auth().attempt({"email": email, "password": password}):
    ...
```
"""

from __future__ import annotations

from fastogram.auth.authenticatable import Authenticatable, MustVerifyEmail
from fastogram.auth.features import features
from fastogram.auth.gate import Gate
from fastogram.auth.guard import auth
from fastogram.auth.password_broker import password_broker
from fastogram.exceptions.types import AuthenticationException, AuthorizationException

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
