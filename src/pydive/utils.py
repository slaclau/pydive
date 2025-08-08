from pydive.dive import Dive


def calculate_decompression_profile(
    bottom_gas, steps=None, points=None, deco_gases=None
):
    if deco_gases is None:
        dive = Dive(bottom_gas)
    else:
        dive = Dive(bottom_gas, deco_gases=deco_gases)
