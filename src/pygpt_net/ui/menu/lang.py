#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2024.01.27 11:00:00                  #
# ================================================== #
from PySide6.QtWidgets import QMenu

from pygpt_net.utils import trans


class Lang:
    def __init__(self, window=None):
        """
        Menu setup

        :param window: Window instance
        """
        self.window = window

    def setup(self):
        """Setup lang menu"""
        self.window.ui.menu['lang'] = {}
        self.window.ui.menu['menu.lang'] = QMenu(trans("menu.lang"), self.window)
