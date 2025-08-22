"""
Cross platform diving application built using BeeWare.
"""

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from pydive_gui.dive_plan import DivePlan
from pydive.gas import air


class PyDive(toga.App):
    dive_plan: DivePlan

    def startup(self):
        self.dive_plan = DivePlan()
        tabs = toga.OptionContainer(content=[("Dive points", self.dive_plan)])
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = tabs
        self.main_window.show()


def main():
    return PyDive()
