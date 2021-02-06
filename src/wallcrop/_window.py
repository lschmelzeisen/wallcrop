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
from typing import Any, Optional

from PIL import Image
from PIL.ImageTk import PhotoImage

_PADDING = 20


class Window:
    def __init__(self, wallpaper: Image.Image):
        self.wallpaper = wallpaper

        root = Tk()
        root.title("wallcrop")
        root.minsize(800, 600)

        root.columnconfigure(0, weight=1)  # type: ignore
        root.rowconfigure(0, weight=1)  # type: ignore

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
        self.canvas.bind("<Configure>", self.resize_canvas_wallpaper)

        label = Label(frame, text="Label")
        label.grid(column=0, row=0, sticky="w")

        button = Button(frame, text="Button")
        button.grid(column=0, row=2, sticky="e")

        root.mainloop()

    def resize_canvas_wallpaper(self, _event: "Event[Any]") -> None:
        aspect_ratio = self.wallpaper.width / self.wallpaper.height

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        wallpaper_width = canvas_width - 2 * _PADDING
        wallpaper_height = int(wallpaper_width / aspect_ratio)

        if wallpaper_height > canvas_height - 2 * _PADDING:
            wallpaper_height = canvas_height - 2 * _PADDING
            wallpaper_width = int(wallpaper_height * aspect_ratio)

        self.canvas_wallpaper = PhotoImage(
            self.wallpaper.resize(
                (wallpaper_width, wallpaper_height),
                Image.LANCZOS,
            )
        )

        self.canvas.delete("wallpaper")  # type: ignore
        self.canvas.create_image(  # type: ignore
            canvas_width / 2,
            canvas_height / 2,
            image=self.canvas_wallpaper,
            anchor="center",
            tags="wallpaper",
        )
