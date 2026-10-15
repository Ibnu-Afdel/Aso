from fastogram.testing.arch import arch_preset


def test_fastogram_preset() -> None:
    arch_preset("fastogram").check()
