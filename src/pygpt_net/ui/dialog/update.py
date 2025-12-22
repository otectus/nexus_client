#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2023.12.25 21:00:00                  #
# ================================================== #

from pygpt_net.ui.widget.dialog.update import UpdateDialog


class Update:
    def __init__(self, window=None):
        """
        Updater dialog

        :param window: Window instance
        """
        self.window = window

    def setup(self):
        """Setup updater dialog"""
        self.window.ui.dialog['update'] = UpdateDialog(self.window)
