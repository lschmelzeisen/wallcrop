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

from pathlib import Path

from nasty_utils import Argument, Program, ProgramConfig
from overrides import overrides
from PIL import Image

import wallcrop
from wallcrop._settings import WallcropSettings
from wallcrop._window import Window


class WallcropProgram(Program):
    class Config(ProgramConfig):
        title = "wallcrop"
        version = wallcrop.__version__
        description = "Multi-monitor wallpaper cropping tool."

    settings: WallcropSettings = Argument(
        alias="config", description="Overwrite default config file path."
    )

    @overrides
    def run(self) -> None:
        wallpaper_path = Path("assets/Nordic Landscape 1125x250.png")
        wallpaper = Image.open(wallpaper_path)
        Window(wallpaper, self.settings.workstations[0])
