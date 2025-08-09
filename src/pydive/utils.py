import logging

from numpy.polynomial import Polynomial as NPPolynomial

logger = logging.getLogger(__name__)


class Polynomial(NPPolynomial):
    def __init__(self, coefficients):
        coefficients.reverse()
        super().__init__(coefficients)
        logger.debug(f"created polynomial with coefficients {coefficients}")

    def roots(self):
        all_roots = NPPolynomial.roots(self)

        def is_real(root):
            return abs(root.real) >= abs(root.imag) * 10**6

        return [root.real for root in all_roots if is_real(root)]


def calculate_decompression_profile(
    bottom_gas, steps=None, points=None, deco_gases=None
):
    if deco_gases is None:
        dive = Dive(bottom_gas)
    else:
        dive = Dive(bottom_gas, deco_gases=deco_gases)
