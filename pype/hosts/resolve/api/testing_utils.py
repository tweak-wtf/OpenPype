#! python3
import os


class TestGUI:
    resolve = bmd.scriptapp("Resolve")  # noqa
    fu = resolve.Fusion()
    ui = fu.UIManager
    disp = bmd.UIDispatcher(fu.UIManager)  # noqa
    title_font = ui.Font({"PixelSize": 18})
    _dialogue = disp.AddWindow(
        {
            "WindowTitle": "Get Testing folder",
            "ID": "TestingWin",
            "Geometry": [250, 250, 250, 100],
            "Spacing": 0,
            "Margin": 10
        },
        [
            ui.VGroup(
                {
                    "Spacing": 2
                },
                [
                    ui.Button(
                        {
                            "ID": "inputTestSourcesFolder",
                            "Text": "Select folder with testing medias",
                            "Weight": 1.25,
                            "ToolTip": (
                                "Chose folder with videos, sequences, "
                                "single images, nested folders with "
                                "medias"
                            ),
                            "Flat": False
                        }
                    ),
                    ui.VGap(),
                    ui.Button(
                        {
                            "ID": "openButton",
                            "Text": "Process Test",
                            "Weight": 2,
                            "ToolTip": "Run the test...",
                            "Flat": False
                        }
                    )
                ]
            )
        ]
    )

    def __init__(self):
        self._widgets = self._dialogue.GetItems()
        self._dialogue.On.TestingWin.Close = self._close_window
        self._dialogue.On.inputTestSourcesFolder.Clicked = self._open_dir_button_pressed  # noqa
        self._dialogue.On.openButton.Clicked = self.process

    def _close_window(self, event):
        self.disp.ExitLoop()

    def process(self, event):
        # placeholder function this supposed to be run from child class
        pass

    def _open_dir_button_pressed(self, event):
        # placeholder function this supposed to be run from child class
        pass

    def show_gui(self):
        self._dialogue.Show()
        self.disp.RunLoop()
        self._dialogue.Hide()
