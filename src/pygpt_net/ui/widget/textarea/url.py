#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2024.11.26 02:00:00                  #
# ================================================== #

from PySide6 import QtCore
from PySide6.QtWidgets import QLineEdit


class UrlInput(QLineEdit):
    def __init__(self, window=None, id=None):
        """
        Url dialog input

        :param window: main window
        :param id: info window id
        """
        super(UrlInput, self).__init__(window)

        self.window = window
        self.id = id

    def keyPressEvent(self, event):
        """
        Key press event

        :param event: key event
        """
        super(UrlInput, self).keyPressEvent(event)

        # save on Enter
        if event.key() == QtCore.Qt.Key_Return or event.key() == QtCore.Qt.Key_Enter:
            self.window.controller.dialogs.confirm.accept_url(
                self.window.ui.dialog['url'].id,
                self.window.ui.dialog['url'].current,
                self.text(),
            )
