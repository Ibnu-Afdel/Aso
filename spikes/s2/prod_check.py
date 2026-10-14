import asyncio, os, sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import exc as sa_exc
from db import DB, Model, configure
from test_s2 import User, Post

async def main(url):
    eng = create_async_engine(url)
    configure(eng)
    async with eng.begin() as c:
        await c.run_sync(Model.metadata.drop_all); await c.run_sync(Model.metadata.create_all)
    async with DB.scope():
        me = await User.create(email="me@x")
        await User.all()                      # read
        try: await User.create(email="me@x")  # failed write
        except sa_exc.IntegrityError: pass
        assert me.email == "me@x"
        async with DB.transaction():
            await User.create(email="t@x")
        try:
            async with DB.transaction():
                await User.create(email="gone@x"); raise RuntimeError
        except RuntimeError: pass
        u = await User.create(email="unsaved@x"); u.email = "changed-not-saved"
    async with DB.scope():                     # new request: what persisted?
        emails = sorted(x.email for x in await User.all())
    print(url.split(":")[0], emails)
    assert emails == ["me@x", "t@x", "unsaved@x"], emails
    await eng.dispose()

asyncio.run(main(sys.argv[1]))
