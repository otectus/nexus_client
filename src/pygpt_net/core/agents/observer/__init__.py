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

from .evaluation import Evaluation

class Observer:
    def __init__(self, window=None):
        self.window = window
        self.evaluation = Evaluation(window)