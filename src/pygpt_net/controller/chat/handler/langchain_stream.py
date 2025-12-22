#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2025.09.05 00:00:00                  #
# ================================================== #

from typing import Optional


def process_langchain_chat(chunk) -> Optional[str]:
    """
    LangChain chat streaming delta.

    :param chunk: Incoming streaming chunk
    :return: Extracted text delta or None
    """
    if getattr(chunk, "content", None) is not None:
        return str(chunk.content)
    return None