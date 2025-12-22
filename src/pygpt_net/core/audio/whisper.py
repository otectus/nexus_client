#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2025.08.29 18:00:00                  #
# ================================================== #

from typing import List

class Whisper:
    def __init__(self, window=None):
        """
        Whisper core

        :param window: Window instance
        """
        self.window = window
        self.voices = [
            "alloy",
            "ash",
            "ballad",
            "coral",
            "echo",
            "fable",
            "nova",
            "onyx",
            "sage",
            "shimmer",
        ]

    def get_voices(self) -> List[str]:
        """
        Get whisper voices

        :return: whisper voice name
        """
        return self.voices