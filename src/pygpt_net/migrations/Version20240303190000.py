#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2024.03.03 22:00:00                  #
# ================================================== #

from sqlalchemy import text

from .base import BaseMigration


class Version20240303190000(BaseMigration):
    def __init__(self, window=None):
        super(Version20240303190000, self).__init__(window)
        self.window = window

    def up(self, conn):
        conn.execute(text("""
        ALTER TABLE ctx_item ADD COLUMN docs_json TEXT;
        """))
