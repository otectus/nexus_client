#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2023.12.31 04:00:00                  #
# ================================================== #

class Info:
    def __init__(self, window=None):
        """
        Info core

        :param window main window
        """
        self.window = window

        # prepare info ids
        self.ids = ['about', 'changelog']
        self.active = {}

        # prepare active
        for id in self.ids:
            self.active[id] = False
