from fastogram.foundation import Application


def create_app():
    return (
        Application.configure(base_path=__file__)
        .with_routing(web="routes/web.py")
        .create()
    )
