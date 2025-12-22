#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2025.09.14 20:00:00                  #
# ================================================== #


class PluginsDebug:
    def __init__(self, window=None):
        """
        Plugins debug

        :param window: Window instance
        """
        self.window = window
        self.id = 'plugins'

    def update(self):
        """Update debug window."""
        debug = self.window.core.debug
        plugins_dict = self.window.core.plugins.plugins

        debug.begin(self.id)

        plugins = list(plugins_dict.keys())
        for key in plugins:
            plugin = plugins_dict[key]
            data = {
                'id': plugin.id,
                'name': plugin.name,
                'description': plugin.description,
                'options': plugin.options
            }
            debug.add(self.id, str(key), str(data))

        debug.end(self.id)
