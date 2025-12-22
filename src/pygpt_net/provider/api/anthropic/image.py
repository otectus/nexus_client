#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2025.09.05 01:00:00                  #
# ================================================== #

from typing import Optional, Dict
from pygpt_net.core.bridge.context import BridgeContext


class Image:
    def __init__(self, window=None):
        self.window = window

    def generate(self, context: BridgeContext, extra: Optional[Dict] = None, sync: bool = True) -> bool:
        """
        Anthropic does not support image generation; only vision input.
        """
        # Inform handlers that nothing was generated
        return False