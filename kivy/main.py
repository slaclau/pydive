import kivy
from kivy.properties import NumericProperty, StringProperty
from kivymd.uix.anchorlayout import MDAnchorLayout

kivy.require("2.1.0")  # replace with your current kivy version !

from kivymd.app import MDApp
from kivymd.uix.tab import MDTabsBase
from kivymd.uix.floatlayout import MDFloatLayout
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.datatables import MDDataTable
from kivy.metrics import sp
from kivy.logger import Logger, LOG_LEVELS
from kivy.core.window import Window

Logger.setLevel(LOG_LEVELS["debug"])


class PDTab(MDFloatLayout, MDTabsBase):
    pass


class PDDiveRow(MDBoxLayout):
    duration = NumericProperty(0)
    depth = NumericProperty(0)
    runtime = StringProperty("0")

    def on_text(self, key, text_field, value):
        Logger.debug(f"{key} field set to {value}")
        try:
            self.__setattr__(key, int(value))
            text_field.error = False
            if key == "duration":
                self.parent.parent.parent.update_runtimes()
        except ValueError:
            text_field.error = True


class PDPlanDive(MDBoxLayout):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_dive_step(self, _button):
        print("add row")
        self.ids.box.add_widget(PDDiveRow())

    def update_runtimes(self):
        for i in range(len(self.ids.box.children) - 2, 0, -1):
            if i == 1:
                self.ids.box.children[i].runtime = str(
                    self.ids.box.children[i].duration
                )
            else:
                self.ids.box.children[i].runtime = str(
                    int(self.ids.box.children[i + 1].runtime)
                    + self.ids.box.children[i].duration
                )


class PDSelectGases(MDBoxLayout):
    pass


class PDWidget(MDBoxLayout):
    def on_tab_switch(self, _tabs, tab, _label, _text):
        Logger.debug(f"PyDive.PDWidget: switching to {tab.key}")


class PyDiveApp(MDApp):
    def build(self):
        return PDWidget()


if __name__ == "__main__":
    import importlib.metadata

    Logger.info(
        f"PyDive: pydive library version is {importlib.metadata.version('pydive')}"
    )
    PyDiveApp().run()
