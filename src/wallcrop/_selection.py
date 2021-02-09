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

from typing import Callable, MutableSet, Optional, Union, cast

import numpy as np
from typing_extensions import Literal

_MOVE_SPEED = 0.01
_MOVE_SPEED_PRECISE = 0.001
_ZOOM_DEFAULT = 0.75
_ZOOM_MIN = 0.1
_ZOOM_SPEED = 0.01
_ZOOM_SPEED_PRECISE = 0.001

T_ZOOM_ANCHOR = Union[
    Literal["center"], Literal["nw"], Literal["ne"], Literal["sw"], Literal["se"]
]


class Selection:
    def __init__(
        self,
        *,
        aspect_ratio: float,
        zoom: float = _ZOOM_DEFAULT,
        position: Optional[np.ndarray] = None,
    ):
        self._aspect_ratio = aspect_ratio
        self.zoom = zoom
        # Use given position or center in available space.
        self.position = position if position else (np.ones(2) - self.zoom) / 2
        self._onchange_callback: MutableSet[Callable[[], None]] = set()

    def register_onchange_handler(self, callback: Callable[[], None]) -> None:
        self._onchange_callback.add(callback)

    def _onchange(self) -> None:
        self.zoom = cast(float, np.clip(self.zoom, _ZOOM_MIN, 1.0))
        self.position = np.clip(self.position, 0.0, 1.0 - self.zoom)

        for callback in self._onchange_callback:
            callback()

    def set_position(self, position: np.ndarray) -> None:
        self.position = position
        self._onchange()

    def move_delta(self, delta: np.ndarray, ignore_aspect_ratio: bool = False) -> None:
        if not ignore_aspect_ratio:
            delta[1] *= self._aspect_ratio
        self.position += delta
        self._onchange()

    def move_left(self, *, precise: bool = False) -> None:
        self.move_delta(
            np.array((-1 * (_MOVE_SPEED if not precise else _MOVE_SPEED_PRECISE), 0.0))
        )

    def move_right(self, *, precise: bool = False) -> None:
        self.move_delta(
            np.array((+1 * (_MOVE_SPEED if not precise else _MOVE_SPEED_PRECISE), 0.0))
        )

    def move_up(self, *, precise: bool = False) -> None:
        self.move_delta(
            np.array((0.0, -1 * (_MOVE_SPEED if not precise else _MOVE_SPEED_PRECISE)))
        )

    def move_down(self, *, precise: bool = False) -> None:
        self.move_delta(
            np.array((0.0, +1 * (_MOVE_SPEED if not precise else _MOVE_SPEED_PRECISE)))
        )

    def set_zoom(self, zoom: float, *, anchor: T_ZOOM_ANCHOR = "center") -> None:
        self.zoom_delta(zoom - self.zoom, anchor=anchor)

    def zoom_delta(self, delta: float, *, anchor: T_ZOOM_ANCHOR = "center") -> None:
        anchor_position = np.array((0.5, 0.5))  # anchor == "center"
        if anchor == "nw":
            anchor_position = np.array((0.0, 0.0))
        elif anchor == "ne":
            anchor_position = np.array((1.0, 0.0))
        elif anchor == "sw":
            anchor_position = np.array((0.0, 1.0))
        elif anchor == "se":
            anchor_position = np.array((1.0, 1.0))
        self.zoom += delta
        self.move_delta(-delta * (1.0 - anchor_position), ignore_aspect_ratio=True)

    def zoom_increase(
        self, *, precise: bool = False, anchor: T_ZOOM_ANCHOR = "center"
    ) -> None:
        self.zoom_delta(
            +1 * (_ZOOM_SPEED if not precise else _ZOOM_SPEED_PRECISE), anchor=anchor
        )

    def zoom_decrease(
        self, *, precise: bool = False, anchor: T_ZOOM_ANCHOR = "center"
    ) -> None:
        self.zoom_delta(
            -1 * (_ZOOM_SPEED if not precise else _ZOOM_SPEED_PRECISE), anchor=anchor
        )
