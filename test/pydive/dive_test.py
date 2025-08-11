import pytest

import pydive.dive as dive
import pydive.gas as gas

class TestDive:
    def test_simple(self):
        simple_dive = dive.Dive(gas.air)
        simple_dive.descend(10, 10)

        assert simple_dive.depth == 10
        assert simple_dive.steps[0].duration == 60
        assert simple_dive.steps[0].depth_change == 10

        simple_dive.stay(5)
        assert simple_dive.depth == 10

        simple_dive.ascend(0)
        assert simple_dive.depth == 0