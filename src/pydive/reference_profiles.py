from pydive.dive import Dive
from pydive.gas import GasBlend, air

reference_dive_1 = Dive(air)
reference_dive_1.default_ascent_rate = 5
reference_dive_1.default_descent_rate = 5
reference_dive_1.descend(20)
reference_dive_1.stay(16)

reference_dive_2 = Dive(air)
reference_dive_2.default_ascent_rate = 5
reference_dive_2.default_descent_rate = 5
reference_dive_2.descend(30)
reference_dive_2.stay(24)

reference_dive_2.deco_gases = {21: GasBlend(oxygen=0.5, nitrogen=0.5)}

reference_dive_3 = Dive(GasBlend(oxygen=0.21, helium=0.35, nitrogen=0.44))
reference_dive_3.default_ascent_rate = 5
reference_dive_3.default_descent_rate = 5
reference_dive_3.descend(45)
reference_dive_3.stay(6)

reference_dive_3.deco_gases = {21: GasBlend(oxygen=0.5, nitrogen=0.5)}
reference_dive_3.decompression_model.last_stop = 3
