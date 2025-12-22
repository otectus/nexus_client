#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2024.03.26 15:00:00                  #
# ================================================== #

from .base import BaseDialog


class ImageDialog(BaseDialog):
    def __init__(self, window=None, id=None):
        """
        Image dialog

        :param window: main window
        :param id: info window id
        """
        super(ImageDialog, self).__init__(window, id)
        self.window = window
        self.id = id
