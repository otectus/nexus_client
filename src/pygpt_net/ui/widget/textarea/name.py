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

from PySide6.QtWidgets import QLineEdit


class NameInput(QLineEdit):
    def __init__(self, window=None, id=None):
        """
        AI or user name input

        :param window: Window instance
        :param id: input id
        """
        super(NameInput, self).__init__(window)
        self.window = window
        self.id = id

    def keyPressEvent(self, event):
        """
        Key press event

        :param event: key event
        """
        super(NameInput, self).keyPressEvent(event)
        self.window.controller.ui.update_tokens()
        self.window.controller.presets.editor.update_from_global(self.id, self.text())
