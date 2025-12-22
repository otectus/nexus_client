#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2024.11.26 04:00:00                  #
# ================================================== #

class PidData():

    def __init__(self, pid, meta=None):
        """Pid Data"""
        self.pid = pid
        self.meta = meta
        self.images_appended = []
        self.urls_appended = []
        self.files_appended = []
        self.buffer = ""
        self.prev_position = None  # previous cursor position (for chunk append)
        self.is_cmd = False
