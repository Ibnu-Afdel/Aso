defaults = {"guard": "web", "passwords": "users"}

guards = {
    "web": {"driver": "session", "provider": "users"},
}

providers = {
    "users": {"driver": "model", "model": "app.models.user.User"},
}
