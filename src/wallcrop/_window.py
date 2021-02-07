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

from tkinter import Canvas, Event, Tk
from tkinter.ttk import Button, Frame, Label
from typing import Any, Callable, Optional, Tuple

from PIL import Image
from PIL.ImageTk import PhotoImage

from wallcrop._settings import WorkstationSettings

_PADDING = 20
_SELECTION_ZOOM_SPEED = 0.01
_SELECTION_ZOOM_MIN = 0.1
_SELECTION_MOVE_SPEED = 0.02


class Window:
    def __init__(self, wallpaper: Image.Image, workstation: WorkstationSettings):
        self.wallpaper = wallpaper
        self.wallpaper_aspect_ratio = self.wallpaper.width / self.wallpaper.height
        self.workstation = workstation

        if not self.workstation.monitors:
            # TODO: move to pydantic validation of settings.
            raise Exception("Need at least one monitor configured per workstation.")

        self.monitor_coord_min = (float("inf"), float("inf"))
        self.monitor_coord_max = (-float("inf"), -float("inf"))
        for monitor in self.workstation.monitors:
            self.monitor_coord_min = (
                min(monitor.position[0], self.monitor_coord_min[0]),
                min(monitor.position[1], self.monitor_coord_min[1]),
            )
            self.monitor_coord_max = (
                max(monitor.position[0] + monitor.size[0], self.monitor_coord_max[0]),
                max(monitor.position[1] + monitor.size[1], self.monitor_coord_max[1]),
            )

        self.selection_pos = (0.0, 0.0)
        self.selection_zoom = 1.0

        root = Tk()
        root.title("wallcrop")
        root.minsize(800, 600)

        root.columnconfigure(0, weight=1)  # type: ignore
        root.rowconfigure(0, weight=1)  # type: ignore

        root.bind("<i>", self.zoom_selection(-1.0))
        root.bind("<o>", self.zoom_selection(+1.0))
        root.bind("<Left>", self.move_selection((-1.0, 0.0)))
        root.bind("<Right>", self.move_selection((1.0, 0.0)))
        root.bind("<Up>", self.move_selection((0.0, -1.0)))
        root.bind("<Down>", self.move_selection((0.0, 1.0)))

        frame = Frame(root, padding=_PADDING)
        frame.grid(column=0, row=0, sticky="n w s e")
        frame.columnconfigure(0, weight=1)  # type: ignore
        frame.rowconfigure(1, weight=1)  # type: ignore

        self.canvas_wallpaper: Optional[PhotoImage] = None
        self.canvas = Canvas(frame)
        self.canvas.configure(
            width=200,
            height=200,
            background="#1D2021",
            borderwidth=0,
            highlightthickness=0,
        )
        self.canvas.grid(column=0, row=1, sticky="n w s e", pady=_PADDING)
        self.canvas.bind("<Configure>", self.redraw_canvas)

        label = Label(frame, text="Label")
        label.grid(column=0, row=0, sticky="w")

        button = Button(frame, text="Button")
        button.grid(column=0, row=2, sticky="e")

        root.mainloop()

    def zoom_selection(self, delta: float) -> Callable[[Optional["Event[Any]"]], None]:
        def event_handler(_event: Optional["Event[Any]"] = None) -> None:
            self.selection_zoom += delta * _SELECTION_ZOOM_SPEED
            self.redraw_canvas()

        return event_handler

    def move_selection(
        self, delta: Tuple[float, float]
    ) -> Callable[[Optional["Event[Any]"]], None]:
        def event_handler(_event: Optional["Event[Any]"] = None) -> None:
            self.selection_pos = (
                self.selection_pos[0]
                + delta[0] / self.wallpaper_aspect_ratio * _SELECTION_MOVE_SPEED,
                self.selection_pos[1] + delta[1] * _SELECTION_MOVE_SPEED,
            )
            self.redraw_canvas()

        return event_handler

    def redraw_canvas(self, _event: "Optional[Event[Any]]" = None) -> None:
        self.selection_zoom = max(_SELECTION_ZOOM_MIN, min(self.selection_zoom, 1.0))
        self.selection_pos = (
            max(0.0, min(self.selection_pos[0], 1.0 - self.selection_zoom)),
            max(0.0, min(self.selection_pos[1], 1.0 - self.selection_zoom)),
        )

        canvas_size = (self.canvas.winfo_width(), self.canvas.winfo_height())

        canvas_wallpaper_size = (
            canvas_size[0] - 2 * _PADDING,
            int((canvas_size[0] - 2 * _PADDING) / self.wallpaper_aspect_ratio),
        )
        if canvas_wallpaper_size[1] > canvas_size[1] - 2 * _PADDING:
            canvas_wallpaper_size = (
                int((canvas_size[1] - 2 * _PADDING) * self.wallpaper_aspect_ratio),
                canvas_size[1] - 2 * _PADDING,
            )

        canvas_wallpaper_position = (
            (canvas_size[0] - canvas_wallpaper_size[0]) / 2,
            (canvas_size[1] - canvas_wallpaper_size[1]) / 2,
        )

        self.canvas_wallpaper = PhotoImage(
            self.wallpaper.resize(canvas_wallpaper_size, Image.LANCZOS)
        )

        self.canvas.delete("wallpaper")  # type: ignore
        self.canvas.create_image(  # type: ignore
            canvas_wallpaper_position[0],
            canvas_wallpaper_position[1],
            image=self.canvas_wallpaper,
            anchor="nw",
            tags="wallpaper",
        )

        for i, monitor in enumerate(self.workstation.monitors):
            monitor_selection_pos = (
                (monitor.position[0] - self.monitor_coord_min[0])
                * (self.selection_zoom / self.monitor_coord_max[0]),
                (monitor.position[1] - self.monitor_coord_min[1])
                * (self.selection_zoom / self.monitor_coord_max[1]),
            )
            monitor_selection_size = (
                monitor.size[0] * (self.selection_zoom / self.monitor_coord_max[0]),
                monitor.size[1] * (self.selection_zoom / self.monitor_coord_max[1]),
            )
            monitor_pos_canvas = (
                (self.selection_pos[0] + monitor_selection_pos[0])
                * canvas_wallpaper_size[0]
                + canvas_wallpaper_position[0],
                (self.selection_pos[1] + monitor_selection_pos[1])
                * canvas_wallpaper_size[1]
                + canvas_wallpaper_position[1],
            )

            self.canvas.delete(f"selection-monitor-{i}")  # type: ignore
            self.canvas.create_rectangle(  # type: ignore
                monitor_pos_canvas[0],
                monitor_pos_canvas[1],
                monitor_pos_canvas[0]
                + monitor_selection_size[0] * canvas_wallpaper_size[0],
                monitor_pos_canvas[1]
                + monitor_selection_size[1] * canvas_wallpaper_size[1],
                outline="yellow",
                tags=f"selection-monitor-{i}",
            )
