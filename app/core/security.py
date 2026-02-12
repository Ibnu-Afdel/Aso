def mask_secret(value: str) -> str:
    if not value:
        return ""
    return f"{value[:4]}...{value[-4:]}"
