#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2025.09.05 18:00:00                  #
# ================================================== #

import json
from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class PromptItem:
    id: Optional[object] = None
    name: Optional[str] = None
    content: Optional[str] = None

    def __init__(self):
        """
        Prompt item
        """
        self.id = None
        self.name = None
        self.content = None

    def serialize(self) -> dict:
        """
        Serialize item to dict

        :return: serialized item
        """
        return {
            'id': str(self.id),
            'name': self.name,
            'content': self.content,
        }

    def deserialize(self, data: dict):
        """
        Deserialize item from dict

        :param data: serialized item
        """
        if 'id' in data:
            self.id = data['id']
        if 'name' in data:
            self.name = data['name']
        if 'content' in data:
            self.content = data['content']

    def dump(self) -> str:
        """
        Dump item to string

        :return: serialized item
        """
        try:
            return json.dumps(self.serialize())
        except Exception as e:
            pass
        return ""

    def __str__(self):
        """To string"""
        return self.dump()