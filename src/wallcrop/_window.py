#
# Copyright 2021 Lukas Schmelzeisen
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from __future__ import annotations

from tkinter import BooleanVar, Menu, Tk, messagebox
from tkinter.ttk import Frame, Label, Spinbox

import numpy as np
from PIL import Image

import wallcrop
from wallcrop._selection import Selection
from wallcrop._selection_widget import SelectionWidget
from wallcrop._settings import WorkstationSettings

_MINSIZE = (800, 600)
_PADDING = 20


class Window:
    def __init__(self, workstation: WorkstationSettings, wallpaper: Image.Image):
        self._root = Tk()
        self._root.title("wallcrop")
        self._root.minsize(*_MINSIZE)

        self._show_monitor_labels = BooleanVar(self._root, value=False)
        self._show_unselected_area = BooleanVar(self._root, value=True)

        frame = Frame(self._root, padding=_PADDING)
        frame.grid(column=0, row=0, sticky="n w s e")
        self._root.columnconfigure(0, weight=1)  # type: ignore
        self._root.rowconfigure(0, weight=1)  # type: ignore

        frame_top = Frame(frame)
        frame_top.grid(column=0, row=0, sticky="n w s e")

        frame_bot = Frame(frame)
        frame_bot.grid(column=0, row=2, sticky="n w s e")

        self._selection = Selection(aspect_ratio=np.divide(*wallpaper.size))
        self._selection.register_onchange_handler(self._reset_spinbox_values)

        self._selection_widget = SelectionWidget(
            parent=frame,
            workstation=workstation,
            wallpaper=wallpaper,
            selection=self._selection,
        )
        self._selection_widget.set_show_monitor_labels(self._show_monitor_labels.get())
        self._selection_widget.set_show_unselected_area(
            self._show_unselected_area.get()
        )
        self._selection_widget.grid(column=0, row=1, sticky="n w s e", pady=_PADDING)
        frame.columnconfigure(0, weight=1)  # type: ignore
        frame.rowconfigure(1, weight=1)  # type: ignore

        label_wallpaper = Label(frame_top, text=workstation.name)
        label_wallpaper.grid(column=0, row=0)

        # Center columns 1-6 on frame_bot.
        frame_bot.columnconfigure(0, weight=1)  # type: ignore
        frame_bot.columnconfigure(7, weight=1)  # type: ignore

        # TODO: Figure out how to not have spinbox show zero when using
        #  increment/decrement buttons.
        label_selection_position_x = Label(frame_bot, text="X: ")
        label_selection_position_x.grid(column=1, row=0)
        self._spinbox_selection_position_x = Spinbox(
            frame_bot, width=5, validate="focusout"
        )
        self._spinbox_selection_position_x.grid(column=2, row=0)

        label_selection_position_y = Label(frame_bot, text="  Y: ")
        label_selection_position_y.grid(column=3, row=0)
        self._spinbox_selection_position_y = Spinbox(
            frame_bot, width=5, validate="focusout"
        )
        self._spinbox_selection_position_y.grid(column=4, row=0)

        label_selection_zoom = Label(frame_bot, text="  Zoom: ")
        label_selection_zoom.grid(column=5, row=0)
        self._spinbox_selection_zoom = Spinbox(frame_bot, width=5, validate="focusout")
        self._spinbox_selection_zoom.grid(column=6, row=0)

        self._bind_actions()
        self._set_up_menubar()
        self._reset_spinbox_values()

    def _bind_actions(self) -> None:
        self._root.bind("<Escape>", lambda _event: self.quit())
        self._root.bind("<q>", lambda _event: self.quit())

        self._root.bind(
            "<m>",
            lambda _event: self._show_monitor_labels.set(
                not (self._show_monitor_labels.get())
            ),
        )
        self._root.bind(
            "<n>",
            lambda _event: self._show_unselected_area.set(
                not (self._show_unselected_area.get())
            ),
        )

        self._root.bind("<i>", lambda _event: self._selection.zoom_increase())
        self._root.bind(
            "<I>", lambda _event: self._selection.zoom_increase(precise=True)
        )

        self._root.bind("<o>", lambda _event: self._selection.zoom_decrease())
        self._root.bind(
            "<O>", lambda _event: self._selection.zoom_decrease(precise=True)
        )

        self._root.bind("<h>", lambda _event: self._selection.move_left())
        self._root.bind("<H>", lambda _event: self._selection.move_left(precise=True))
        self._root.bind("<Left>", lambda _event: self._selection.move_left())
        self._root.bind(
            "<Shift-Left>", lambda _event: self._selection.move_left(precise=True)
        )

        self._root.bind("<l>", lambda _event: self._selection.move_right())
        self._root.bind("<L>", lambda _event: self._selection.move_right(precise=True))
        self._root.bind("<Right>", lambda _event: self._selection.move_right())
        self._root.bind(
            "<Shift-Right>", lambda _event: self._selection.move_right(precise=True)
        )

        self._root.bind("<k>", lambda _event: self._selection.move_up())
        self._root.bind("<K>", lambda _event: self._selection.move_up(precise=True))
        self._root.bind("<Up>", lambda _event: self._selection.move_up())
        self._root.bind(
            "<Shift-Up>", lambda _event: self._selection.move_up(precise=True)
        )

        self._root.bind("<j>", lambda _event: self._selection.move_down())
        self._root.bind("<J>", lambda _event: self._selection.move_down(precise=True))
        self._root.bind("<Down>", lambda _event: self._selection.move_down())
        self._root.bind(
            "<Shift-Down>", lambda _event: self._selection.move_down(precise=True)
        )

        self._spinbox_selection_position_x.configure(
            validatecommand=lambda *_args: self._set_selection_position_x()
        )
        self._spinbox_selection_position_x.bind(
            "<Return>", lambda _event: self._set_selection_position_x()  # type: ignore
        )
        self._spinbox_selection_position_x.bind(
            "<<Decrement>>", lambda _event: self._selection.move_left()
        )
        self._spinbox_selection_position_x.bind(
            "<<Increment>>", lambda _event: self._selection.move_right()
        )

        self._spinbox_selection_position_y.configure(
            validatecommand=lambda *_args: self._set_selection_position_y()
        )
        self._spinbox_selection_position_y.bind(
            "<Return>", lambda _event: self._set_selection_position_y()  # type: ignore
        )
        self._spinbox_selection_position_y.bind(
            "<<Decrement>>", lambda _event: self._selection.move_up()
        )
        self._spinbox_selection_position_y.bind(
            "<<Increment>>", lambda _event: self._selection.move_down()
        )

        self._spinbox_selection_zoom.configure(
            validatecommand=lambda *_args: self._set_selection_zoom()
        )
        self._spinbox_selection_zoom.bind(
            "<Return>", lambda _event: self._set_selection_zoom()  # type: ignore
        )
        self._spinbox_selection_zoom.bind(
            "<<Decrement>>", lambda _event: self._selection.zoom_decrease()
        )
        self._spinbox_selection_zoom.bind(
            "<<Increment>>", lambda _event: self._selection.zoom_increase()
        )

        self._show_monitor_labels.trace_add(
            "write",
            lambda *_args: self._selection_widget.set_show_monitor_labels(
                self._show_monitor_labels.get()
            ),
        )
        self._show_unselected_area.trace_add(
            "write",
            lambda *_args: self._selection_widget.set_show_unselected_area(
                self._show_unselected_area.get()
            ),
        )

    def _set_up_menubar(self) -> None:
        # TODO: check that this look good on macOS, as described here:
        #   https://tkdocs.com/tutorial/menus.html#platformmenus

        self._root.option_add("*tearOff", False)

        menu = Menu(self._root)

        menu_file = Menu(menu)
        menu_file.add_command(  # type: ignore
            label="Quit", underline=0, accelerator="Q, Escape", command=self.quit
        )
        menu.add_cascade(menu=menu_file, label="File", underline=0)  # type: ignore

        menu_view = Menu(menu)
        menu_view.add_checkbutton(  # type: ignore
            label="Label Monitors",
            variable=self._show_monitor_labels,
            underline=6,
            accelerator="M",
        )
        menu_view.add_checkbutton(  # type: ignore
            label="Show Unselected",
            variable=self._show_unselected_area,
            underline=6,
            accelerator="N",
        )
        menu.add_cascade(menu=menu_view, label="View", underline=0)  # type: ignore

        menu_help = Menu(menu, name="help")
        menu_help.add_command(  # type: ignore
            label="About Wallcrop",
            underline=0,
            command=lambda: messagebox.showinfo(
                parent=self._root,
                title="About Wallcrop",
                message=f"Wallcrop {wallcrop.__version__}",
                detail=(
                    "Copyright 2021 Lukas Schmelzeisen.\n"
                    "Licensed under the Apache License, Version 2.0.\n"
                    "https://github.com/lschmelzeisen/wallcrop/"
                ),
            ),
        )
        menu.add_cascade(menu=menu_help, label="Help", underline=1)  # type: ignore

        self._root["menu"] = menu

    def mainloop(self) -> None:
        self._root.mainloop()

    def quit(self) -> None:
        self._root.destroy()

    def _set_selection_position_x(self) -> bool:
        try:
            value = float(self._spinbox_selection_position_x.get())  # type: ignore
        except ValueError:
            self._spinbox_selection_position_x.set(self._selection.position[0])
            return False
        self._selection.set_position(np.array((value, self._selection.position[1])))
        return True

    def _set_selection_position_y(self) -> bool:
        try:
            value = float(self._spinbox_selection_position_y.get())  # type: ignore
        except ValueError:
            self._spinbox_selection_position_y.set(self._selection.position[1])
            return False
        self._selection.set_position(np.array((self._selection.position[0], value)))
        return True

    def _set_selection_zoom(self) -> bool:
        try:
            value = float(self._spinbox_selection_zoom.get())  # type: ignore
        except ValueError:
            self._spinbox_selection_zoom.set(self._selection.zoom)
            return False
        self._selection.set_zoom(value)
        return True

    def _reset_spinbox_values(self) -> None:
        self._spinbox_selection_position_x.set(f"{self._selection.position[0]:.3f}")
        self._spinbox_selection_position_y.set(f"{self._selection.position[1]:.3f}")
        self._spinbox_selection_zoom.set(f"{self._selection.zoom:.3f}")
