#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2024.01.02 11:00:00                  #
# ================================================== #

from pygpt_net.item.model import ModelItem


def test_integrity():
    """Test ModeItem integrity"""
    item = ModelItem()

    assert item.id is None
    assert item.name is None
    assert item.mode == ["chat"]
    assert item.langchain == {}
    assert item.ctx == 0
    assert item.tokens == 0
    assert item.default is False
