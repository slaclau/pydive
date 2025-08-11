import pytest

import pydive.gas as gas


class TestGasBlend:
    def test_create_trimix(self):
        trimix_10_70 = gas.GasBlend(oxygen=0.1, helium=0.7, nitrogen=0.2)

        assert trimix_10_70.fraction("oxygen") == 0.1
        assert round(trimix_10_70.min_operating_depth) == 6

    def test_helper_functions(self):
        O2 = gas.GasBlend(oxygen=1)
        assert O2.fraction("oxygen") == 1
        assert O2.fraction("nitrogen") == 0
        assert round(O2.max_operating_depth) == 6
        assert O2.min_operating_depth == 0
        assert O2.partial_pressure("oxygen", 10) == 2

    def test_unknown_gas(self):
        with pytest.raises(ValueError):
            unknown_blend = gas.GasBlend(unknown=1)

    def test_incomplete_blend(self):
        with pytest.raises(ValueError):
            incomplete_blend = gas.GasBlend(oxygen=80)

class TestGas:
    def test_get_gas_type(self):
        assert gas.Oxygen == gas.Gas.get_gas_type("oxygen")
        assert gas.Oxygen == gas.Gas.get_gas_type(gas.Oxygen)
        with pytest.raises(ValueError):
            gas.Gas.get_gas_type("unknown")

if __name__ == '__main__':
    pytest.main()
