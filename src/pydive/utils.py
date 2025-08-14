import logging
import math

from numpy.polynomial import Polynomial as NPPolynomial

logger = logging.getLogger(__name__)


class Polynomial:
    def __init__(self, coefficients):
        coefficients.reverse()
        self.coef = coefficients

    def roots(self):
        if len(self.coef) == 4:
            coefficients = self.coef
            if coefficients[-2] == 0 and coefficients[-1] == 1:
                b = -coefficients[-3]
                c = -coefficients[-4]
                discriminant = 27 * c**2 - 4 * b**3
                if discriminant < 0:
                    return [
                        2
                        * (b / 3) ** 0.5
                        * math.cos(math.acos(3 * c * (3 / b) ** 0.5 / (2 * b)) / 3)
                    ]
                denominator = (9 * c + (3 * discriminant) ** 0.5) ** (1 / 3)
                return [
                    (2 / 3) ** (1 / 3) * b / denominator + denominator / 18 ** (1 / 3)
                ]

        all_roots = NPPolynomial(self.coef).roots()

        def is_real(root):
            return abs(root.real) >= abs(root.imag) * 10**6

        return [root.real for root in all_roots if is_real(root)]
