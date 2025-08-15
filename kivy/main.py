import kivy

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


class Tab(MDFloatLayout, MDTabsBase):
    pass


class PDPlanDive(MDBoxLayout):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data_tables = MDDataTable(
            column_data=[
                ("Depth", sp(20)),
                ("Duration", sp(20)),
                ("Runtime", sp(20)),
                ("Gas", sp(20)),
            ],
        )
        self.add_widget(self.data_tables)

    def add_dive_step(self, _button):
        self.data_tables.add_row([0, 0, 0, 0])


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
