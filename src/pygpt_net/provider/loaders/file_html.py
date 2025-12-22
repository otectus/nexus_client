#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2025.08.06 01:00:00                  #
# ================================================== #

from llama_index.core.readers.base import BaseReader

from .base import BaseLoader


class Loader(BaseLoader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = "html"
        self.name = "HTML files"
        self.extensions = ["html", "htm"]
        self.type = ["file"]
        self.init_args = {
            "tag": "section",
            "ignore_no_id": False,
        }
        self.init_args_types = {
            "tag": "str",
            "ignore_no_id": "bool",
        }

    def get(self) -> BaseReader:
        """
        Get reader instance

        :return: Data reader instance
        """
        from llama_index.readers.file.html import HTMLTagReader
        args = self.get_args()
        return HTMLTagReader(**args)
