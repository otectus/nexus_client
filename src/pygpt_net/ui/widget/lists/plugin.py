#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2024.01.12 08:00:00                  #
# ================================================== #

from pygpt_net.ui.widget.lists.base import BaseList


class PluginList(BaseList):
    def __init__(self, window=None, id=None):
        """
        Plugin select menu (in settings dialog)

        :param window: main window
        :param id: parent id
        """
        super(PluginList, self).__init__(window)
        self.window = window
        self.id = id

    def click(self, val):
        idx = val.row()
        self.window.ui.tabs['plugin.settings'].setCurrentIndex(idx)
        self.window.controller.plugins.set_by_tab(idx)

