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
_SEL_ZOOM_SPEED = 0.01
_SEL_ZOOM_MIN = 0.1
_SEL_MOVE_SPEED = 0.01
_CANVAS_BG = "#1D2021"
_SEL_BG = "#282828"
_SEL_BG_ALPHA = "AA"


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

        self.sel_pos = np.array((0.0, 0.0))
        self.sel_zoom_factor = 1.0

        self.last_canvas_size = np.array([0.0, 0.0])
        self.resized_wall = self.wall
        self.canvas_wall: Optional[PhotoImage] = None
        self.sel = self.wall
        self.sel_draw = Draw(self.sel)
        self.canvas_sel: Optional[PhotoImage] = None

        self.blacken_unselected = False

        root = Tk()
        root.title("wallcrop")
        root.minsize(*_GUI_MINSIZE)

        root.columnconfigure(0, weight=1)  # type: ignore
        root.rowconfigure(0, weight=1)  # type: ignore

        sel_zoom_in = self.sel_zoom(-1.0)
        sel_zoom_out = self.sel_zoom(+1.0)
        sel_move_left = self.sel_move((-1.0, 0.0))
        sel_move_right = self.sel_move((+1.0, 0.0))
        sel_move_up = self.sel_move((0.0, -1.0))
        sel_move_down = self.sel_move((0.0, +1.0))

        root.bind("<Escape>", lambda _event: root.destroy())
        root.bind("<i>", sel_zoom_in)
        root.bind("<o>", sel_zoom_out)
        root.bind("<Left>", sel_move_left)
        root.bind("<Right>", sel_move_right)
        root.bind("<Up>", sel_move_up)
        root.bind("<Down>", sel_move_down)
        root.bind("<b>", self.toggle_blacken_unselected)

        frame = Frame(root, padding=_GUI_PADDING)
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
        self.canvas.bind("<Configure>", self.redraw_canvas)

        label = Label(frame, text="Label")
        label.grid(column=0, row=0, sticky="w")

        button = Button(frame, text="Button")
        button.grid(column=0, row=2, sticky="e")

        root.mainloop()

    def sel_zoom(self, delta: float) -> Callable[[Optional[Event[Any]]], None]:
        def event_handler(_event: Optional[Event[Any]] = None) -> None:
            self.sel_zoom_factor += delta * _SEL_ZOOM_SPEED
            self.redraw_canvas()

        return event_handler

    def sel_move(
        self, delta: Tuple[float, float]
    ) -> Callable[[Optional[Event[Any]]], None]:
        def event_handler(_event: Optional[Event[Any]] = None) -> None:
            aspect_delta = np.array((delta[0], delta[1] * self.wall_aspect))
            self.sel_pos += aspect_delta * _SEL_MOVE_SPEED
            self.redraw_canvas()

        return event_handler

    def toggle_blacken_unselected(self, _event: Optional[Event[Any]] = None) -> None:
        self.blacken_unselected = not self.blacken_unselected
        self.redraw_canvas()

    def redraw_canvas(self, _event: "Optional[Event[Any]]" = None) -> None:
        self.sel_zoom_factor = max(_SEL_ZOOM_MIN, min(self.sel_zoom_factor, 1.0))
        self.sel_pos = np.maximum(
            0.0, np.minimum(1.0 - self.sel_zoom_factor, self.sel_pos)
        )

        canvas_size = np.array((self.canvas.winfo_width(), self.canvas.winfo_height()))
        canvas_wall_size = np.array(((canvas_size[0] - 2 * _GUI_PADDING), 0))
        canvas_wall_size[1] = int(canvas_wall_size[0] / self.wall_aspect)
        if canvas_wall_size[1] > canvas_size[1] - 2 * _GUI_PADDING:
            canvas_wall_size[1] = canvas_size[1] - 2 * _GUI_PADDING
            canvas_wall_size[0] = int(canvas_wall_size[1] * self.wall_aspect)
        canvas_wall_pos = (canvas_size - canvas_wall_size) / 2

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

            self.canvas.delete("wall")  # type: ignore
            self.canvas.create_image(  # type: ignore
                *canvas_wall_pos,
                image=self.canvas_wall,
                anchor="nw",
                tags="wall",
            )

        self.sel.paste(
            _SEL_BG + ("FF" if self.blacken_unselected else _SEL_BG_ALPHA),
            (0, 0, *self.sel.size),
        )

        for mon in self.workstation.monitors:
            mon_sel_size = (
                np.array(mon.size) * self.sel_zoom_factor / self.mon_coord_max
            )
            mon_sel_pos = (np.array(mon.position) - self.mon_coord_min) * (
                self.sel_zoom_factor / self.mon_coord_max
            )
            mon_canvas_pos1 = (self.sel_pos + mon_sel_pos) * canvas_wall_size
            mon_canvas_pos2 = mon_canvas_pos1 + mon_sel_size * canvas_wall_size

            self.sel_draw.rectangle((*mon_canvas_pos1, *mon_canvas_pos2), "#FFFFFF00")

        self.canvas_sel = PhotoImage(self.sel)
        self.canvas.delete("sel")  # type: ignore
        self.canvas.create_image(  # type: ignore
            *canvas_wall_pos,
            image=self.canvas_sel,
            anchor="nw",
            tags="sel",
        )
