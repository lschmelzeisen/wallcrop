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

from itertools import cycle
from tkinter import BooleanVar, Canvas, Event, Menu, Tk, messagebox
from tkinter.ttk import Frame, Label, Spinbox
from typing import Any, Callable, Optional, Tuple, cast

import numpy as np
from mypy_extensions import DefaultArg
from PIL import Image
from PIL.ImageDraw import Draw
from PIL.ImageTk import PhotoImage

import wallcrop
from wallcrop._settings import WorkstationSettings

# Abbreviations used in this implementation:
# - aspect: aspect ratio
# - mon: monitor
# - pos: position
# - sel: selection
# - wall: wall

_TKINTER_SHIFT = 0x1  # https://stackoverflow.com/a/61998948/211404
_GUI_MINSIZE = (800, 600)
_GUI_PADDING = 20
_GUI_REDRAW_FPS = 60
_SEL_ZOOM_DEFAULT = 0.75
_SEL_ZOOM_MIN = 0.1
_SEL_ZOOM_SPEED = 0.01
_SEL_MOVE_SPEED = 0.01
_SEL_PRECISE_FACTOR = 1 / 10
_CANVAS_BG = "#1D2021"
_SEL_BG_COLOR = "#282828"
_SEL_BG_ALPHA = "AA"
_MON_LABEL_COLORS = (
    ("#FB4934", "#B8BB26", "FABD2F", "#83A598", "#D3869B", "#8EC07C", "#FE8019")
    + ("#CC241D", "#98971A", "#D79921", "#458588", "#B16286", "#689D6A", "#D65D0E")
    + ("#9D0006", "#79740E", "#B57614", "#076678", "#8F3F71", "#427B58", "#AF3A03")
)
_MON_LABEL_ALPHA = "33"


class Window:
    def __init__(self, workstation: WorkstationSettings, wallpaper: Image.Image):
        self.workstation = workstation
        self.wall = wallpaper
        self.wall_size = np.array(wallpaper.size)
        self.wall_aspect = np.divide(*self.wall_size)

        if not self.workstation.monitors:
            # TODO: move to pydantic validation of settings.
            raise Exception("Need at least one monitor configured per workstation.")

        self.mon_coord_min = np.array((float("inf"), float("inf")))
        self.mon_coord_max = np.array((-float("inf"), -float("inf")))
        for mon in self.workstation.monitors:
            # TODO: convert settings to np.array while parsing
            self.mon_coord_min = np.minimum(np.array(mon.position), self.mon_coord_min)
            self.mon_coord_max = np.maximum(
                np.array(mon.position) + np.array(mon.size),
                self.mon_coord_max,
            )

        self.sel_zoom_factor = _SEL_ZOOM_DEFAULT
        self.sel_pos = (np.ones(2) - self.sel_zoom_factor) / 2  # Center selection.

        self.canvas_size = np.array((0.0, 0.0))
        self.canvas_wall_size = np.array((0.0, 0.0))
        self.canvas_wall_pos = np.array((0.0, 0.0))
        self.last_canvas_size = np.array((0.0, 0.0))
        self.resized_wall = self.wall
        self.canvas_wall: Optional[PhotoImage] = None
        self.sel = self.wall
        self.sel_draw = Draw(self.sel)
        self.canvas_sel: Optional[PhotoImage] = None

        self.redraw_scheduled = False
        self.mouse_moving = False
        self.mouse_zooming = False
        self.mouse_zooming_anchor: Optional[np.ndarray] = None
        self.mouse_last_pos = np.array((0.0, 0.0))

        sel_move_left = self.sel_move((-_SEL_MOVE_SPEED, 0.0))
        sel_move_right = self.sel_move((+_SEL_MOVE_SPEED, 0.0))
        sel_move_up = self.sel_move((0.0, -_SEL_MOVE_SPEED))
        sel_move_down = self.sel_move((0.0, +_SEL_MOVE_SPEED))
        sel_zoom_in = self.sel_zoom(-_SEL_ZOOM_SPEED)
        sel_zoom_out = self.sel_zoom(+_SEL_ZOOM_SPEED)

        self.root = Tk()
        self.root.title("wallcrop")
        self.root.minsize(*_GUI_MINSIZE)

        self.label_monitors = BooleanVar(self.root, value=False)
        self.label_monitors.trace_add("write", self.schedule_redraw)
        self.show_unselected = BooleanVar(self.root, value=True)
        self.show_unselected.trace_add("write", self.schedule_redraw)

        self.root.bind("<Escape>", self.exit)
        self.root.bind("<q>", self.exit)
        self.root.bind(
            "<m>",
            lambda _event: self.label_monitors.set(not (self.label_monitors.get())),
        )
        self.root.bind(
            "<n>",
            lambda _event: self.show_unselected.set(not (self.show_unselected.get())),
        )
        self.root.bind("<i>", sel_zoom_in)
        self.root.bind("<I>", sel_zoom_in)
        self.root.bind("<o>", sel_zoom_out)
        self.root.bind("<O>", sel_zoom_out)
        self.root.bind("<Left>", sel_move_left)
        self.root.bind("<Shift-Left>", sel_move_left)
        self.root.bind("<h>", sel_move_left)
        self.root.bind("<H>", sel_move_left)
        self.root.bind("<Right>", sel_move_right)
        self.root.bind("<Shift-Right>", sel_move_right)
        self.root.bind("<l>", sel_move_right)
        self.root.bind("<L>", sel_move_right)
        self.root.bind("<Up>", sel_move_up)
        self.root.bind("<Shift-Up>", sel_move_up)
        self.root.bind("<k>", sel_move_up)
        self.root.bind("<K>", sel_move_up)
        self.root.bind("<Down>", sel_move_down)
        self.root.bind("<Shift-Down>", sel_move_down)
        self.root.bind("<j>", sel_move_down)
        self.root.bind("<J>", sel_move_down)

        self.root.option_add("*tearOff", False)
        menu = Menu(self.root)

        menu_file = Menu(menu)
        menu_file.add_command(
            label="Quit", underline=0, accelerator="Q, Escape", command=self.exit
        )
        menu.add_cascade(menu=menu_file, label="File", underline=0)

        menu_view = Menu(menu)
        menu_view.add_checkbutton(
            label="Label Monitors",
            variable=self.label_monitors,
            underline=6,
            accelerator="M",
        )
        menu_view.add_checkbutton(
            label="Show Unselected",
            variable=self.show_unselected,
            underline=6,
            accelerator="N",
        )
        menu.add_cascade(menu=menu_view, label="View", underline=0)

        menu_help = Menu(menu, name="help")
        menu_help.add_command(
            label="About Wallcrop",
            underline=0,
            command=lambda: messagebox.showinfo(
                parent=self.root,
                title="About Wallcrop",
                message=f"Wallcrop {wallcrop.__version__}",
                detail=(
                    "Copyright 2021 Lukas Schmelzeisen.\n"
                    "Licensed under the Apache License, Version 2.0.\n"
                    "https://github.com/lschmelzeisen/wallcrop/"
                ),
            ),
        )
        menu.add_cascade(menu=menu_help, label="Help", underline=1)

        # TODO: check that this look good on macOS, as decribed here:
        #   https://tkdocs.com/tutorial/menus.html#platformmenus
        self.root["menu"] = menu

        frame = Frame(self.root, padding=_GUI_PADDING)
        frame.grid(column=0, row=0, sticky="n w s e")
        self.root.columnconfigure(0, weight=1)  # type: ignore
        self.root.rowconfigure(0, weight=1)  # type: ignore

        self.canvas = Canvas(frame)
        self.canvas.configure(
            background=_CANVAS_BG,
            borderwidth=0,
            highlightthickness=0,
        )
        self.canvas.grid(column=0, row=1, sticky="n w s e", pady=_GUI_PADDING)
        frame.columnconfigure(0, weight=1)  # type: ignore
        frame.rowconfigure(1, weight=1)  # type: ignore

        # TODO: check if these keybinds work on Windows/macOS
        self.canvas.bind("<Motion>", self.mouse_motion)
        self.canvas.bind("<ButtonPress-1>", self.start_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self.stop_mouse_move)
        self.canvas.bind("<ButtonPress-3>", self.start_mouse_zoom)
        self.canvas.bind("<ButtonRelease-3>", self.stop_mouse_zoom)
        self.canvas.bind("<ButtonPress-4>", sel_zoom_out)
        self.canvas.bind("<Shift-ButtonPress-4>", sel_zoom_out)
        self.canvas.bind("<ButtonPress-5>", sel_zoom_in)
        self.canvas.bind("<Shift-ButtonPress-5>", sel_zoom_in)
        self.canvas.bind("<Configure>", self.schedule_redraw)

        frame_top = Frame(frame)
        frame_top.grid(column=0, row=0, sticky="n w s e")

        label_wallpaper = Label(frame_top, text=workstation.name)
        label_wallpaper.grid(column=0, row=0)

        frame_bot = Frame(frame)
        frame_bot.grid(column=0, row=2, sticky="n w s e")
        frame_bot.columnconfigure(0, weight=1)  # type: ignore
        frame_bot.columnconfigure(7, weight=1)  # type: ignore

        label_sel_pos_x = Label(frame_bot, text="X: ")
        label_sel_pos_x.grid(column=1, row=0)
        self.spinbox_sel_pos_x = Spinbox(
            frame_bot, width=5, validate="focusout", validatecommand=self.sel_set_pos_x
        )
        self.spinbox_sel_pos_x.bind("<Return>", self.sel_set_pos_x)  # type: ignore
        self.spinbox_sel_pos_x.bind("<<Decrement>>", sel_move_left)
        self.spinbox_sel_pos_x.bind("<<Increment>>", sel_move_right)
        self.spinbox_sel_pos_x.grid(column=2, row=0)

        label_sel_pos_y = Label(frame_bot, text="  Y: ")
        label_sel_pos_y.grid(column=3, row=0)
        self.spinbox_sel_pos_y = Spinbox(
            frame_bot, width=5, validate="focusout", validatecommand=self.sel_set_pos_y
        )
        self.spinbox_sel_pos_y.bind("<Return>", self.sel_set_pos_y)  # type: ignore
        self.spinbox_sel_pos_y.bind("<<Decrement>>", sel_move_up)
        self.spinbox_sel_pos_y.bind("<<Increment>>", sel_move_down)
        self.spinbox_sel_pos_y.grid(column=4, row=0)

        label_sel_zoom_factor = Label(frame_bot, text="  Zoom: ")
        label_sel_zoom_factor.grid(column=5, row=0)
        self.spinbox_sel_zoom_factor = Spinbox(
            frame_bot,
            width=5,
            validate="focusout",
            validatecommand=self.sel_set_zoom_factor,
        )
        self.spinbox_sel_zoom_factor.bind(
            "<Return>", self.sel_set_zoom_factor  # type: ignore
        )
        self.spinbox_sel_zoom_factor.grid(column=6, row=0)
        self.spinbox_sel_zoom_factor.bind("<<Decrement>>", sel_zoom_out)
        self.spinbox_sel_zoom_factor.bind("<<Increment>>", sel_zoom_in)

        self.root.mainloop()

    def exit(self, _event: Optional[Event[Any]] = None) -> None:
        self.root.destroy()

    def sel_move(
        self, delta: Tuple[float, float]
    ) -> Callable[[DefaultArg(Optional[Event[Any]])], None]:
        def event_handler(event: Optional[Event[Any]] = None) -> None:
            d = np.array(delta)
            if event and cast(int, event.state) & _TKINTER_SHIFT:
                d *= _SEL_PRECISE_FACTOR
            self.sel_pos += np.array((d[0], d[1] * self.wall_aspect))
            self.schedule_redraw()

        return event_handler

    def sel_zoom(
        self, delta: float, anchor: np.ndarray = np.array((0.5, 0.5))  # noqa: B008
    ) -> Callable[[DefaultArg(Optional[Event[Any]])], None]:
        def event_handler(event: Optional[Event[Any]] = None) -> None:
            d = delta
            if event and cast(int, event.state) & _TKINTER_SHIFT:
                d *= _SEL_PRECISE_FACTOR
            self.sel_zoom_factor += d
            self.sel_pos -= (1.0 - anchor) * np.repeat(d, 2)
            self.schedule_redraw()

        return event_handler

    def sel_set_pos_x(self, _event: Optional[Event[Any]] = None) -> bool:
        try:
            self.sel_pos[0] = float(self.spinbox_sel_pos_x.get())  # type: ignore
            self.schedule_redraw()
        except ValueError:
            self.spinbox_sel_pos_x.set(self.sel_pos[0])
        return False

    def sel_set_pos_y(self, _event: Optional[Event[Any]] = None) -> bool:
        try:
            self.sel_pos[1] = float(self.spinbox_sel_pos_y.get())  # type: ignore
            self.schedule_redraw()
        except ValueError:
            self.spinbox_sel_pos_y.set(self.sel_pos[1])
        return False

    def sel_set_zoom_factor(self, _event: Optional[Event[Any]] = None) -> bool:
        try:
            self.sel_zoom_factor = float(
                self.spinbox_sel_zoom_factor.get()  # type: ignore
            )
            self.schedule_redraw()
        except ValueError:
            self.spinbox_sel_zoom_factor.set(self.sel_zoom_factor)
        return False

    def start_mouse_move(self, event: Event[Any]) -> None:
        self.mouse_last_pos = np.array((event.x, event.y))
        self.mouse_moving = True

    def stop_mouse_move(self, _event: Event[Any]) -> None:
        self.mouse_moving = False

    def start_mouse_zoom(self, event: Event[Any]) -> None:
        self.mouse_last_pos = np.array((event.x, event.y))
        self.mouse_zooming = True
        canvas_sel_center = self.canvas_wall_pos + self.canvas_wall_size * (
            self.sel_pos + self.sel_zoom_factor / 2
        )
        self.mouse_zooming_anchor = self.mouse_last_pos > canvas_sel_center

    def stop_mouse_zoom(self, _event: Event[Any]) -> None:
        self.mouse_zooming = False
        self.mouse_zooming_anchor = None

    def mouse_motion(self, event: Event[Any]) -> None:
        mouse_pos = np.array((event.x, event.y))

        if self.mouse_moving:
            self.sel_pos += (mouse_pos - self.mouse_last_pos) / self.canvas_size
            self.schedule_redraw()

        if self.mouse_zooming:
            assert self.mouse_zooming_anchor is not None
            # Check if we are moving closer to the off-screen corner corresponding to
            # our zoom anchor, and zoom in or out corresponding to that.
            anchor = (self.mouse_zooming_anchor - 0.5) * 1e7
            zoom_direction = 1 - 2 * int(
                np.linalg.norm(anchor - mouse_pos)
                > np.linalg.norm(anchor - self.mouse_last_pos)
            )

            self.sel_zoom(
                zoom_direction
                * np.linalg.norm(mouse_pos - self.mouse_last_pos)
                / np.linalg.norm(self.canvas_size),
                anchor=self.mouse_zooming_anchor,
            )()

            self.schedule_redraw()

        self.mouse_last_pos = mouse_pos

    def schedule_redraw(self, *_args: object) -> None:
        if not self.redraw_scheduled:
            self.redraw_scheduled = True
            self.root.after(1000 // _GUI_REDRAW_FPS, self.redraw)

    def redraw(self, _event: "Optional[Event[Any]]" = None) -> None:
        self.sel_zoom_factor = max(_SEL_ZOOM_MIN, min(self.sel_zoom_factor, 1.0))
        self.sel_pos = np.clip(self.sel_pos, 0.0, 1.0 - self.sel_zoom_factor)

        # We first set the spinbox values to empty to prevent a bug where we would else
        # select their contents when clicking the increment/decrement buttons.
        self.spinbox_sel_pos_x.set("")
        self.spinbox_sel_pos_y.set("")
        self.spinbox_sel_zoom_factor.set("")
        self.spinbox_sel_pos_x.set(f"{self.sel_pos[0]:.3f}")
        self.spinbox_sel_pos_y.set(f"{self.sel_pos[1]:.3f}")
        self.spinbox_sel_zoom_factor.set(f"{self.sel_zoom_factor:.3f}")

        self.canvas_size = np.array(
            (self.canvas.winfo_width(), self.canvas.winfo_height())
        )
        self.canvas_wall_size = np.array(((self.canvas_size[0] - 2 * _GUI_PADDING), 0))
        self.canvas_wall_size[1] = int(self.canvas_wall_size[0] / self.wall_aspect)
        if self.canvas_wall_size[1] > self.canvas_size[1] - 2 * _GUI_PADDING:
            self.canvas_wall_size[1] = self.canvas_size[1] - 2 * _GUI_PADDING
            self.canvas_wall_size[0] = int(self.canvas_wall_size[1] * self.wall_aspect)

        if not np.array_equal(self.canvas_size, self.last_canvas_size):
            self.last_canvas_size = self.canvas_size

            self.resized_wall = self.wall.resize(
                cast(Tuple[int, int], tuple(self.canvas_wall_size)), Image.LANCZOS
            )
            self.canvas_wall = PhotoImage(self.resized_wall)

            self.sel = Image.new(
                "RGBA", cast(Tuple[int, int], tuple(self.canvas_wall_size.astype(int)))
            )
            self.sel_draw = Draw(self.sel)

            self.canvas_wall_pos = (self.canvas_size - self.canvas_wall_size) / 2
            self.canvas.delete("wall")  # type: ignore
            self.canvas.create_image(  # type: ignore
                *self.canvas_wall_pos,
                image=self.canvas_wall,
                anchor="nw",
                tags="wall",
            )
            self.canvas.delete("sel")  # type: ignore
            self.canvas.create_image(  # type: ignore
                *self.canvas_wall_pos,
                image=self.canvas_sel,
                anchor="nw",
                tags="sel",
            )

        self.sel.paste(
            _SEL_BG_COLOR + (_SEL_BG_ALPHA if self.show_unselected.get() else "FF"),
            (0, 0, *self.sel.size),
        )

        for mon, mon_label_color in zip(
            self.workstation.monitors, cycle(_MON_LABEL_COLORS)
        ):
            mon_sel_size = (
                np.array(mon.size) * self.sel_zoom_factor / self.mon_coord_max
            )
            mon_sel_pos = (np.array(mon.position) - self.mon_coord_min) * (
                self.sel_zoom_factor / self.mon_coord_max
            )
            mon_canvas_pos1 = (self.sel_pos + mon_sel_pos) * self.canvas_wall_size
            mon_canvas_pos2 = mon_canvas_pos1 + mon_sel_size * self.canvas_wall_size

            self.sel_draw.rectangle(
                (*mon_canvas_pos1, *mon_canvas_pos2),
                "#FFFFFF00"
                if not self.label_monitors.get()
                else mon_label_color + _MON_LABEL_ALPHA,
            )
            if self.label_monitors.get():
                self.sel_draw.text(
                    tuple(mon_canvas_pos1),
                    f"{mon.name}\n({mon.resolution[0]}x{mon.resolution[1]})",
                    mon_label_color + "FF",
                )

        self.canvas_sel = PhotoImage(self.sel)
        self.canvas.itemconfig("sel", image=self.canvas_sel)

        self.redraw_scheduled = False
