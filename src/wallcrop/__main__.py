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

from sys import argv
from typing import Tuple, Union, cast

from wallcrop._cli import WallcropProgram


def main(*args: Union[None, str]) -> None:
    if not args:
        args = tuple(argv[1:])
    elif None in args:
        args = ()
    WallcropProgram.init(*cast(Tuple[str], args)).run()


if __name__ == "__main__":
    main()
