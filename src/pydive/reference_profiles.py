from pydive.dive import Dive
from pydive.gas import GasBlend, air
from pydive.models.decompression.buhlmann import BuhlmannZHL16C
from pydive.models.decompression.vpm_b import VPMB

models = [
    "buhlmann-zhl-16c",
    "vpm-b",
]


def reference_dive(number, model):
    match model:
        case "buhlmann-zhl-16c":
            model_type = BuhlmannZHL16C
        case "vpm-b":
            model_type = VPMB

    match number:
        case 1:
            dive = Dive(air, model=model_type)
            dive.default_ascent_rate = 5
            dive.default_descent_rate = 5
            dive.descend(20)
            dive.stay(16)
            dive.decompression_model.last_stop = 3
        case 2:
            dive = Dive(air, model=model_type)
            dive.default_ascent_rate = 5
            dive.default_descent_rate = 5
            dive.descend(30)
            dive.stay(24)
            dive.deco_gases = {21: GasBlend(oxygen=0.5, nitrogen=0.5)}
        case 3:
            dive = Dive(
                GasBlend(oxygen=0.21, helium=0.35, nitrogen=0.44), model=model_type
            )
            dive.default_ascent_rate = 5
            dive.default_descent_rate = 5
            dive.descend(45)
            dive.stay(6)
            dive.deco_gases = {21: GasBlend(oxygen=0.5, nitrogen=0.5)}
            dive.decompression_model.last_stop = 3
        case 4:
            dive = Dive(
                GasBlend(oxygen=0.18, helium=0.45, nitrogen=0.37), model=model_type
            )
            if model == "buhlmann-zhl-16c":
                dive.decompression_model.low_gf = 0.4
                dive.decompression_model.high_gf = 0.85
            dive.default_ascent_rate = 5
            dive.default_descent_rate = 5
            dive.descend(60)
            dive.stay(8)
            dive.deco_gases = {21: GasBlend(oxygen=0.5, nitrogen=0.5)}
            dive.decompression_model.last_stop = 3
        case 5:
            dive = Dive(
                GasBlend(oxygen=0.21, helium=0.20, nitrogen=0.59), model=model_type
            )
            if model == "buhlmann-zhl-16c":
                dive.decompression_model.low_gf = 0.5
                dive.decompression_model.high_gf = 0.8
            dive.default_ascent_rate = 5
            dive.default_descent_rate = 5
            dive.descend(40)
            dive.stay(2)
            dive.ascend(30)
            dive.stay(16)
            dive.descend(40)
            dive.stay(2)
            dive.decompression_model.last_stop = 3
    return dive


if __name__ == "__main__":
    import time

    for i in range(1, 6):
        for model in models:
            dive = reference_dive(i, model)
            print(f"dive {i} with {model}")
            t = time.time()
            stops = dive.decompress()
            print(dive.markdown)
            for stop in stops:
                print(stop)
            print(f"algorithm took {(time.time() - t)*1000:.0f} ms")
            print(f"runtime was {dive.duration/60:.1f} mins")
            print(dive.models["pulmonary"])
            print(f"{dive.models["cns"]} cns")
            print(f"{dive.models["decompression"]} deco loading")
            print(dive.models["consumption"])
            print("-" * 60)
