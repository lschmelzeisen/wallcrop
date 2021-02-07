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
from tkinter import Canvas, Event, Tk
from tkinter.ttk import Button, Frame, Label
from typing import Any, Callable, Optional, Tuple, cast

import numpy as np
from PIL import Image
from PIL.ImageDraw import Draw
from PIL.ImageTk import PhotoImage

from wallcrop._settings import WorkstationSettings

# Abbreviations used in this implementation:
# - aspect: aspect ratio
# - mon: monitor
# - pos: position
# - sel: selection
# - wall: wall

_GUI_MINSIZE = (800, 600)
_GUI_PADDING = 20
_GUI_REDRAW_FPS = 30
_SEL_DEFAULT_ZOOM = 0.75
_SEL_ZOOM_SPEED = 0.01
_SEL_ZOOM_MIN = 0.1
_SEL_MOVE_SPEED = 0.01
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
        self.wall = wallpaper.convert("RGBA")
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

        self.sel_zoom_factor = _SEL_DEFAULT_ZOOM
        self.sel_pos = (np.ones(2) - self.sel_zoom_factor) / 2  # Center selection.

        self.last_canvas_size = np.array([0.0, 0.0])
        self.resized_wall = self.wall
        self.canvas_wall: Optional[PhotoImage] = None
        self.sel = self.wall
        self.sel_draw = Draw(self.sel)
        self.canvas_sel: Optional[PhotoImage] = None

        self.redraw_scheduled = False

        self.label_monitors = False
        self.show_unselected = False

        self.root = Tk()
        self.root.title("wallcrop")
        self.root.minsize(*_GUI_MINSIZE)

        self.root.columnconfigure(0, weight=1)  # type: ignore
        self.root.rowconfigure(0, weight=1)  # type: ignore

        sel_zoom_in = self.sel_zoom(-1.0)
        sel_zoom_out = self.sel_zoom(+1.0)
        sel_move_left = self.sel_move((-1.0, 0.0))
        sel_move_right = self.sel_move((+1.0, 0.0))
        sel_move_up = self.sel_move((0.0, -1.0))
        sel_move_down = self.sel_move((0.0, +1.0))

        self.root.bind("<Escape>", lambda _event: self.root.destroy())
        self.root.bind("<i>", sel_zoom_in)
        self.root.bind("<o>", sel_zoom_out)
        self.root.bind("<Left>", sel_move_left)
        self.root.bind("<h>", sel_move_left)
        self.root.bind("<Right>", sel_move_right)
        self.root.bind("<l>", sel_move_right)
        self.root.bind("<Up>", sel_move_up)
        self.root.bind("<k>", sel_move_up)
        self.root.bind("<Down>", sel_move_down)
        self.root.bind("<j>", sel_move_down)
        self.root.bind("<m>", self.toggle_label_monitors)
        self.root.bind("<n>", self.toggle_show_unselected)

        frame = Frame(self.root, padding=_GUI_PADDING)
        frame.grid(column=0, row=0, sticky="n w s e")
        frame.columnconfigure(0, weight=1)  # type: ignore
        frame.rowconfigure(1, weight=1)  # type: ignore

        self.canvas = Canvas(frame)
        self.canvas.configure(
            background=_CANVAS_BG,
            borderwidth=0,
            highlightthickness=0,
        )
        self.canvas.grid(column=0, row=1, sticky="n w s e", pady=_GUI_PADDING)
        self.canvas.bind("<Configure>", self.redraw)

        label = Label(frame, text="Label")
        label.grid(column=0, row=0, sticky="w")

        button = Button(frame, text="Button")
        button.grid(column=0, row=2, sticky="e")

        self.root.mainloop()

    def sel_zoom(self, delta: float) -> Callable[[Optional[Event[Any]]], None]:
        def event_handler(_event: Optional[Event[Any]] = None) -> None:
            self.sel_zoom_factor += delta * _SEL_ZOOM_SPEED
            self.schedule_redraw()

        return event_handler

    def sel_move(
        self, delta: Tuple[float, float]
    ) -> Callable[[Optional[Event[Any]]], None]:
        def event_handler(_event: Optional[Event[Any]] = None) -> None:
            aspect_delta = np.array((delta[0], delta[1] * self.wall_aspect))
            self.sel_pos += aspect_delta * _SEL_MOVE_SPEED

            self.schedule_redraw()

        return event_handler

    def toggle_label_monitors(self, _event: Optional[Event[Any]] = None) -> None:
        self.label_monitors = not self.label_monitors
        self.schedule_redraw()

    def toggle_show_unselected(self, _event: Optional[Event[Any]] = None) -> None:
        self.show_unselected = not self.show_unselected
        self.schedule_redraw()

    def schedule_redraw(self) -> None:
        if not self.redraw_scheduled:
            self.redraw_scheduled = True
            self.root.after(1000 // _GUI_REDRAW_FPS, self.redraw)

    def redraw(self, _event: "Optional[Event[Any]]" = None) -> None:
        self.sel_zoom_factor = max(_SEL_ZOOM_MIN, min(self.sel_zoom_factor, 1.0))
        self.sel_pos = np.clip(self.sel_pos, 0.0, 1.0 - self.sel_zoom_factor)

        canvas_size = np.array((self.canvas.winfo_width(), self.canvas.winfo_height()))
        canvas_wall_size = np.array(((canvas_size[0] - 2 * _GUI_PADDING), 0))
        canvas_wall_size[1] = int(canvas_wall_size[0] / self.wall_aspect)
        if canvas_wall_size[1] > canvas_size[1] - 2 * _GUI_PADDING:
            canvas_wall_size[1] = canvas_size[1] - 2 * _GUI_PADDING
            canvas_wall_size[0] = int(canvas_wall_size[1] * self.wall_aspect)

        if not np.array_equal(canvas_size, self.last_canvas_size):
            self.last_canvas_size = canvas_size

            self.resized_wall = self.wall.resize(
                cast(Tuple[int, int], tuple(canvas_wall_size)), Image.LANCZOS
            )
            self.canvas_wall = PhotoImage(self.resized_wall)

            self.sel = Image.new(
                "RGBA", cast(Tuple[int, int], tuple(canvas_wall_size.astype(int)))
            )
            self.sel_draw = Draw(self.sel)

            canvas_wall_pos = (canvas_size - canvas_wall_size) / 2
            self.canvas.delete("wall")  # type: ignore
            self.canvas.create_image(  # type: ignore
                *canvas_wall_pos,
                image=self.canvas_wall,
                anchor="nw",
                tags="wall",
            )
            self.canvas.delete("sel")  # type: ignore
            self.canvas.create_image(  # type: ignore
                *canvas_wall_pos,
                image=self.canvas_sel,
                anchor="nw",
                tags="sel",
            )

        self.sel.paste(
            _SEL_BG_COLOR + (_SEL_BG_ALPHA if not self.show_unselected else "FF"),
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
            mon_canvas_pos1 = (self.sel_pos + mon_sel_pos) * canvas_wall_size
            mon_canvas_pos2 = mon_canvas_pos1 + mon_sel_size * canvas_wall_size

            self.sel_draw.rectangle(
                (*mon_canvas_pos1, *mon_canvas_pos2),
                "#FFFFFF00"
                if not self.label_monitors
                else mon_label_color + _MON_LABEL_ALPHA,
            )
            if self.label_monitors:
                self.sel_draw.text(
                    tuple(mon_canvas_pos1),
                    f"{mon.name}\n({mon.resolution[0]}x{mon.resolution[1]})",
                    mon_label_color + "FF",
                )

        self.canvas_sel = PhotoImage(self.sel)
        self.canvas.itemconfig("sel", image=self.canvas_sel)

        self.redraw_scheduled = False
