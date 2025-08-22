import logging

import toga
from toga.style.pack import COLUMN, ROW

logger = logging.getLogger(__name__)


class DivePointRow(toga.Box):
    def __init__(self):
        super().__init__()
        self.add(
            toga.Button(
                icon="resources/user-trash-symbolic", on_press=self.delete, width=48
            )
        )
        self.depth_input = toga.NumberInput(flex=1)
        self.duration_input = toga.NumberInput(
            value=0, flex=1, on_change=self.call_update_runtimes
        )
        self.runtime_label = toga.Label("", flex=1)
        self.add(self.depth_input)
        self.add(self.duration_input)
        self.add(self.runtime_label)

    def delete(self, _):
        self.parent.remove_row(self)

    def call_update_runtimes(self, _):
        self.parent.update_runtimes(self)


class DivePlan(toga.Box):
    def __init__(self):
        super().__init__(direction=COLUMN)
        label_box = toga.Box()
        label_box.add(toga.Label("", width=48))
        label_box.add(toga.Label("Depth (m)", flex=1))
        label_box.add(toga.Label("Duration (min)", flex=1))
        label_box.add(toga.Label("Runtime (min)", flex=1))
        self.add(label_box)
        self.add_button = toga.Button("Add dive step", on_press=self.add_dive_step)
        self.add(self.add_button)

    def add_dive_step(self, _):
        logger.debug("add dive step")
        row = DivePointRow()
        self.insert(self.index(self.add_button), row)
        self.update_runtimes(row)

    def update_runtimes(self, row):
        index = self.index(row)
        for i in range(index, len(self.children) - 1):
            if i == 1:
                self.children[i].runtime_label.text = str(
                    self.children[i].duration_input.value
                )
            else:
                self.children[i].runtime_label.text = (
                    int(self.children[i - 1].runtime_label.text)
                    + self.children[i].duration_input.value
                )

    def remove_row(self, row):
        index = self.index(row)
        self.remove(row)
        self.update_runtimes(self.children[index])
