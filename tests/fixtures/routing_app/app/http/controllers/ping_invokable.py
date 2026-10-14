from fastogram.http import Controller


class PingInvokable(Controller):
    """A single-action controller (T-13): `Route.post("/invoke/{n}", PingInvokable)`."""

    async def __call__(self, n: int):
        return {"invoked": n}
