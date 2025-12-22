#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2024.11.17 03:00:00                  #
# ================================================== #

from pygpt_net.ui.widget.lists.base import BaseList


class ModeList(BaseList):
    def __init__(self, window=None, id=None):
        """
        Presets select menu

        :param window: main window
        :param id: input id
        """
        super(ModeList, self).__init__(window)
        self.window = window
        self.id = id

    def click(self, val):
        #self.window.controller.mode.select(val.row())
        self.selection = self.selectionModel().selection()
