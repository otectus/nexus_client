#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2025.02.01 11:00:00                  #
# ================================================== #

from pygpt_net.item.model import ModelItem


class Gpt:
    def __init__(self, window=None):
        """
        GPT prompt templates

        :param window: Window instance
        """
        self.window = window

    def get(
            self,
            prompt: str,
            mode: str = None,
            model: ModelItem = None
    ) -> str:
        """
        Get system prompt content

        CMD/TOOL EXECUTE prompts:
         - cmd
         - cmd.extra
         - cmd.extra.assistants

        :param prompt: id of the prompt
        :param mode: mode
        :param model: model item
        :return: text content
        """
        key = "prompt." + prompt
        if self.window.core.config.has(key):
            return str(self.window.core.config.get(key))
        return ""