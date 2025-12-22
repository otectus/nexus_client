#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2025.09.01 23:00:00                  #
# ================================================== #

from PySide6.QtWidgets import QVBoxLayout, QWidget

from pygpt_net.ui.widget.option.combo import OptionCombo
from pygpt_net.ui.widget.option.slider import OptionSlider


class Image:
    def __init__(self, window=None):
        """
        Toolbox UI

        :param window: Window instance
        """
        self.window = window

    def setup(self) -> QWidget:
        """
        Setup image

        :return: QWidget
        :rtype: QWidget
        """
        option = {
            "type": "int",
            "slider": True,
            "label": "img_variants",
            "min": 1,
            "max": 4,
            "step": 1,
            "value": 1,
            "multiplier": 1,
        }

        ui = self.window.ui
        conf_global = ui.config['global']

        container = QWidget()
        ui.nodes['dalle.options'] = container

        conf_global['img_variants'] = OptionSlider(self.window, 'global', 'img_variants', option)

        option_resolutions = self.window.core.image.get_resolution_option()
        conf_global['img_resolution'] = OptionCombo(self.window, 'global', 'img_resolution', option_resolutions)

        rows = QVBoxLayout()
        rows.addWidget(conf_global['img_variants'])
        rows.addWidget(conf_global['img_resolution'])
        rows.setContentsMargins(2, 5, 5, 5)

        container.setLayout(rows)
        container.setContentsMargins(2, 0, 0, 0)

        return container