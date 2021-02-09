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

from tkinter import Canvas, Event, Misc
from typing import Any, Tuple

import numpy as np
from PIL import Image
from PIL.ImageDraw import Draw
from PIL.ImageTk import PhotoImage

from wallcrop._selection import T_ZOOM_ANCHOR, Selection
from wallcrop._settings import WorkstationSettings


def _hex_color_to_rgba(c: str) -> Tuple[int, int, int, int]:
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16), int(c[7:9], 16)


_REDRAW_FPS = 60
_PADDING = 20
_BG_COLOR = "#1D2021"
_SELECTION_VISUAL_BG_COLOR = "#282828"
_SELECTION_VISUAL_BG_ALPHA = "AA"
_MONITOR_LABEL_COLORS = (
    ("#FB4934", "#B8BB26", "FABD2F", "#83A598", "#D3869B", "#8EC07C", "#FE8019")
    + ("#CC241D", "#98971A", "#D79921", "#458588", "#B16286", "#689D6A", "#D65D0E")
    + ("#9D0006", "#79740E", "#B57614", "#076678", "#8F3F71", "#427B58", "#AF3A03")
)
_MONITOR_LABEL_ALPHA = "33"

_PALETTE = (
    (
        *_hex_color_to_rgba("FFFFFF00"),
        *_hex_color_to_rgba(_SELECTION_VISUAL_BG_COLOR + _SELECTION_VISUAL_BG_ALPHA),
        *_hex_color_to_rgba(_SELECTION_VISUAL_BG_COLOR + "FF"),
    )
    + tuple(
        color_byte
        for monitor_label_color in _MONITOR_LABEL_COLORS
        for color_byte in _hex_color_to_rgba(monitor_label_color + "FF")
    )
    + tuple(
        color_byte
        for monitor_label_color in _MONITOR_LABEL_COLORS
        for color_byte in _hex_color_to_rgba(monitor_label_color + _MONITOR_LABEL_ALPHA)
    )
)
_PALETTE_INDEX_TRANSPARENT = 0
_PALETTE_INDEX_BG_TRANSPARENT = 1
_PALETTE_INDEX_BG_OPAQUE = 2
_PALETTE_INDEX_OFFSET_MONITOR_LABELS = 3
_PALETTE_INDEX_OFFSET_MONITOR_LABELS_TRANSPARENT = 3 + len(_MONITOR_LABEL_COLORS)


class SelectionWidget(Canvas):
    def __init__(
        self,
        *,
        parent: Misc,
        workstation: WorkstationSettings,
        wallpaper: Image.Image,
        selection: Selection,
    ):
        super().__init__(
            parent,
            background=_BG_COLOR,
            borderwidth=0,
            highlightthickness=0,
        )

        self._workstation = workstation
        self._workstation_coord_min = np.array((np.inf, np.inf))
        self._workstation_coord_max = np.array((-np.inf, -np.inf))
        for monitor in self._workstation.monitors:
            # TODO: convert settings to np.array while parsing
            self._workstation_coord_min = np.minimum(
                np.array(monitor.position), self._workstation_coord_min
            )
            self._workstation_coord_max = np.maximum(
                np.array(monitor.position) + np.array(monitor.size),
                self._workstation_coord_max,
            )

        self._canvas_size = np.ones(2)
        self._canvas_wallpaper_size = np.ones(2)
        self._canvas_wallpaper_position = np.zeros(2)

        self._wallpaper = wallpaper
        self._wallpaper_size = np.array(self._wallpaper.size)
        self._wallpaper_aspect_ratio = np.divide(*self._wallpaper_size)
        self._wallpaper_resized = self._wallpaper
        self._selection_visual = Image.new("RGBA", (1, 1))
        self._selection_visual_draw = Draw(self._selection_visual)
        self._canvas_image_wallpaper = PhotoImage(self._wallpaper_resized)
        self._canvas_image_selection_visual = PhotoImage(self._selection_visual)

        self._selection = selection
        self._selection.register_onchange_handler(self.schedule_redraw)

        self._redraw_scheduled = False
        self._resize_scheduled = False
        self._show_monitor_labels = False
        self._show_unselected_area = True

        self._mouse_moving = False
        self._mouse_zooming = False
        self._mouse_zooming_anchor = np.zeros(2)
        self._mouse_last_coords = np.zeros(2)

        self._bind_actions()
        self._schedule_resize()

    def _bind_actions(self) -> None:
        # TODO: check if these keybindings work on Windows/macOS.
        self.bind("<Configure>", lambda _event: self._schedule_resize())
        self.bind("<ButtonPress-1>", self._start_mouse_moving)
        self.bind("<ButtonRelease-1>", self._stop_mouse_moving)
        self.bind("<ButtonPress-3>", self._start_mouse_zooming)
        self.bind("<ButtonRelease-3>", self._stop_mouse_zooming)
        self.bind("<Motion>", self._handle_mouse_motion)
        self.bind(
            "<ButtonPress-4>",
            lambda _event: self._selection.zoom_increase(),
        )
        self.bind(
            "<Shift-ButtonPress-4>",
            lambda _event: self._selection.zoom_increase(precise=True),
        )
        self.bind(
            "<ButtonPress-5>",
            lambda _event: self._selection.zoom_decrease(),
        )
        self.bind(
            "<Shift-ButtonPress-5>",
            lambda _event: self._selection.zoom_decrease(precise=True),
        )

    def set_show_monitor_labels(self, value: bool) -> None:
        self._show_monitor_labels = value
        self.schedule_redraw()

    def set_show_unselected_area(self, value: bool) -> None:
        self._show_unselected_area = value
        self.schedule_redraw()

    def _start_mouse_moving(self, event: Event[Any]) -> None:
        self._mouse_moving = True
        self._mouse_last_coords = np.array((event.x, event.y))

    def _stop_mouse_moving(self, _event: Event[Any]) -> None:
        self._mouse_moving = False

    def _start_mouse_zooming(self, event: Event[Any]) -> None:
        self._mouse_zooming = True
        self._mouse_last_coords = np.array((event.x, event.y))
        canvas_selection_center = (
            self._selection.position + self._selection.zoom / 2
        ) * self._canvas_wallpaper_size + self._canvas_wallpaper_position
        self._mouse_zooming_anchor = self._mouse_last_coords > canvas_selection_center

    def _stop_mouse_zooming(self, _event: Event[Any]) -> None:
        self._mouse_zooming = False

    def _handle_mouse_motion(self, event: Event[Any]) -> None:
        mouse_coords = np.array((event.x, event.y))

        if self._mouse_moving:
            self._selection.move_delta(
                (mouse_coords - self._mouse_last_coords) / self._canvas_wallpaper_size,
                ignore_aspect_ratio=True,
            )
            self.schedule_redraw()

        if self._mouse_zooming:
            zoom_anchor: T_ZOOM_ANCHOR = "center"
            if np.array_equal(self._mouse_zooming_anchor, (False, False)):
                zoom_anchor = "nw"
            elif np.array_equal(self._mouse_zooming_anchor, (True, False)):
                zoom_anchor = "ne"
            elif np.array_equal(self._mouse_zooming_anchor, (False, True)):
                zoom_anchor = "sw"
            elif np.array_equal(self._mouse_zooming_anchor, (True, True)):
                zoom_anchor = "se"

            zoom_corner = (self._mouse_zooming_anchor - 0.5) * 1e9
            zoom_direction = 1 - 2 * int(
                np.linalg.norm(zoom_corner - mouse_coords)
                > np.linalg.norm(zoom_corner - self._mouse_last_coords)
            )
            zoom_delta = np.linalg.norm(
                mouse_coords - self._mouse_last_coords
            ) / np.linalg.norm(self._canvas_wallpaper_size)
            self._selection.zoom_delta(zoom_direction * zoom_delta, anchor=zoom_anchor)

            self.schedule_redraw()

        self._mouse_last_coords = mouse_coords

    def _schedule_resize(self) -> None:
        self._canvas_size = np.array((self.winfo_width(), self.winfo_height()))
        if np.any(self._canvas_size <= 1.0):
            # On program launch the event for this function will fire multiple times.
            # For our calculations (in self._redraw()) to succeed we need to wait until
            # the true window size will have been established.
            return

        self._canvas_wallpaper_size = np.zeros(2)
        self._canvas_wallpaper_size[0] = self._canvas_size[0] - 2 * _PADDING
        self._canvas_wallpaper_size[1] = int(
            self._canvas_wallpaper_size[0] / self._wallpaper_aspect_ratio
        )
        if self._canvas_wallpaper_size[1] > self._canvas_size[1] - 2 * _PADDING:
            self._canvas_wallpaper_size[1] = self._canvas_size[1] - 2 * _PADDING
            self._canvas_wallpaper_size[0] = int(
                self._canvas_wallpaper_size[1] * self._wallpaper_aspect_ratio
            )

        self._resize_scheduled = True
        self.schedule_redraw()

    def schedule_redraw(self, *, force: bool = False) -> None:
        if not self._redraw_scheduled or force:
            self._redraw_scheduled = True
            self.after(1000 // _REDRAW_FPS, self._redraw)

    def _redraw(self) -> None:
        if self._resize_scheduled:
            self._resize_images()
            self._resize_scheduled = False

        self._selection_visual.paste(
            _PALETTE_INDEX_BG_TRANSPARENT
            if self._show_unselected_area
            else _PALETTE_INDEX_BG_OPAQUE,
            (0, 0, *self._selection_visual.size),
        )
        self._draw_monitors_on_selection()
        self._canvas_image_selection_visual = PhotoImage(self._selection_visual)
        self.itemconfig("selection_visual", image=self._canvas_image_selection_visual)

        self._redraw_scheduled = False

    def _resize_images(self) -> None:
        self._wallpaper_resized = self._wallpaper.resize(
            (int(self._canvas_wallpaper_size[0]), int(self._canvas_wallpaper_size[1])),
            Image.LANCZOS,
        )
        self._canvas_image_wallpaper = PhotoImage(self._wallpaper_resized)

        self._selection_visual = Image.new(
            "P",
            (int(self._canvas_wallpaper_size[0]), int(self._canvas_wallpaper_size[1])),
        )
        self._selection_visual.putpalette(_PALETTE, rawmode="RGBA")
        self._selection_visual_draw = Draw(self._selection_visual)

        self._canvas_wallpaper_position = (
            self._canvas_size - self._canvas_wallpaper_size
        ) / 2
        self.delete("wallpaper")  # type: ignore
        self.create_image(  # type: ignore
            *self._canvas_wallpaper_position,
            image=self._canvas_image_wallpaper,
            anchor="nw",
            tags="wallpaper",
        )
        self.delete("selection_visual")  # type: ignore
        self.create_image(  # type: ignore
            *self._canvas_wallpaper_position,
            image=self._canvas_image_selection_visual,
            anchor="nw",
            tags="selection_visual",
        )

    def _draw_monitors_on_selection(self) -> None:
        for monitor_num, monitor in enumerate(self._workstation.monitors):
            monitor_position_on_selection = (
                np.array(monitor.position) - self._workstation_coord_min
            ) * (self._selection.zoom / self._workstation_coord_max)
            monitor_size_on_selection = np.array(monitor.size) * (
                self._selection.zoom / self._workstation_coord_max
            )

            monitor_nw_position_on_canvas = (
                self._selection.position + monitor_position_on_selection
            ) * self._canvas_wallpaper_size
            monitor_se_position_on_canvas = monitor_nw_position_on_canvas + (
                monitor_size_on_selection * self._canvas_wallpaper_size
            )

            self._selection_visual_draw.rectangle(
                (*monitor_nw_position_on_canvas, *monitor_se_position_on_canvas),
                _PALETTE_INDEX_TRANSPARENT
                if not self._show_monitor_labels
                else _PALETTE_INDEX_OFFSET_MONITOR_LABELS_TRANSPARENT + monitor_num,
            )
            if self._show_monitor_labels:
                self._selection_visual_draw.text(
                    (
                        monitor_nw_position_on_canvas[0],
                        monitor_nw_position_on_canvas[1],
                    ),
                    f"{monitor.name}\n"
                    f"({monitor.resolution[0]}x{monitor.resolution[1]})",
                    _PALETTE_INDEX_OFFSET_MONITOR_LABELS + monitor_num,
                )
