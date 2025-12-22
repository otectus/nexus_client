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

from typing import Optional
from pygpt_net.core.bridge.context import MultimodalContext


class Audio:
    def __init__(self, window=None):
        """
        Audio helpers for Anthropic (currently no official input/output audio in Python SDK).

        :param window: Window instance
        """
        self.window = window

    def build_input_block(self, multimodal_ctx: Optional[MultimodalContext]) -> Optional[dict]:
        """
        Future hook: build input_audio block if Anthropic exposes it publicly.
        Currently returns None to avoid 400 errors.
        """
        return None