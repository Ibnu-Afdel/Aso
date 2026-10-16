from aso.routing import Route
from aso.session import session


async def home():
    return {"ok": True}


async def write():
    s = session()
    s.put("hits", s.get("hits", 0) + 1)
    return {"id": s.id(), "hits": s.get("hits")}


async def show_previous():
    return {"previous_url": session().get("_previous_url")}


async def flash_now():
    session().flash("notice", "hello")
    return {"ok": True}


async def read_flash():
    return {"notice": session().get("notice")}


async def unsafe_post():
    return {"ok": True}


async def unsafe_put():
    return {"ok": True}


async def regenerate():
    session().regenerate()
    return {"id": session().id()}


async def invalidate():
    session().invalidate()
    return {"id": session().id()}


async def stuff(size: int):
    session().put("blob", "x" * size)
    return {"ok": True}


Route.get("/", home).name("home")
Route.get("/write", write).name("write")
Route.get("/previous", show_previous).name("previous")
Route.get("/flash-now", flash_now).name("flash_now")
Route.get("/read-flash", read_flash).name("read_flash")
Route.post("/unsafe", unsafe_post).name("unsafe.post")
Route.put("/unsafe", unsafe_put).name("unsafe.put")
Route.post("/regenerate", regenerate).name("regenerate")
Route.post("/invalidate", invalidate).name("invalidate")
Route.get("/stuff/{size}", stuff).name("stuff")
