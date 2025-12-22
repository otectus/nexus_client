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

from pygpt_net.item.ctx import CtxItem


class BaseProvider:
    def __init__(self, window=None):
        self.window = window
        self.id = ""
        self.type = "history"

    def attach(self, window):
        self.window = window

    def install(self):
        pass

    def append(self, ctx: CtxItem, mode: str):
        pass

    def truncate(self):
        pass
