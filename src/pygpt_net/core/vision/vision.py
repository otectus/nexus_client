#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2024.11.18 00:00:00                  #
# ================================================== #

from .analyzer import Analyzer

class Vision:
    def __init__(self, window=None):
        """
        Audio analyzer

        :param window: Window instance
        """
        self.window = window
        self.analyzer = Analyzer(window)