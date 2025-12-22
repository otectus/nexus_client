#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2025.09.05 18:00:00                  #
# ================================================== #

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class ModeItem:
    id: Optional[object] = None
    name: str = ""
    label: str = ""
    default: bool = False