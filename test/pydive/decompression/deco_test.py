import pytest

import pandas as pd

from pydive.reference_profiles import models, reference_dive

numbers = list(range(1, 6))

@pytest.mark.parametrize("model", models)
@pytest.mark.parametrize("number", numbers)
def test_regression(number, model):
    csv_path = f"test_data/ref_dive_{number}_{model}.csv"
    df = pd.read_csv(csv_path, parse_dates=["time"])
    dive = reference_dive(number, model)
    dive.decompress()
    assert df.equals(dive.df)