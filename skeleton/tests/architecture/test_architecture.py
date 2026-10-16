from aso.testing.arch import arch_preset


def test_aso_preset() -> None:
    arch_preset("aso").check()
