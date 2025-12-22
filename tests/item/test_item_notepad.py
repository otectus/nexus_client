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

from pygpt_net.item.notepad import NotepadItem


def test_integrity():
    """Test NotepadItem integrity"""
    item = NotepadItem()

    assert item.id == 0
    assert item.uuid is None
    assert item.idx == 0
    assert item.title == ""
    assert item.content == ""
    assert item.deleted is False
    assert item.created == item.updated
    assert item.initialized is False

    assert type(item.created) == int
    assert item.created == item.updated
