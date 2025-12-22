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
        self.id = "pdf"
        self.name = "PDF documents"
        self.extensions = ["pdf"]
        self.type = ["file"]
        self.init_args = {
            "return_full_document": False,
        }
        self.init_args_types = {
            "return_full_document": "bool",
        }

    def get(self) -> BaseReader:
        """
        Get reader instance

        :return: Data reader instance
        """
        from llama_index.readers.file.docs import PDFReader
        args = self.get_args()
        return PDFReader(**args)
