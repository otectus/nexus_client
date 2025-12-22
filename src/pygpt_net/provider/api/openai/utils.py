#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2024.11.26 19:00:00                  #
# ================================================== #

import re


def sanitize_name(name: str) -> str:
    """
    Sanitize name

    :param name: name
    :return: sanitized name
    """
    if name is None:
        return ""
    # allowed characters: a-z, A-Z, 0-9, _, and -
    name = name.strip().lower()
    sanitized_name = re.sub(r'[^a-z0-9_-]', '_', name)
    return sanitized_name[:64]  # limit to 64 characters