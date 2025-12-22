#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2023.12.31 23:00:00                  #
# ================================================== #

from sqlalchemy import text

from .base import BaseMigration


class Version20231231230000(BaseMigration):
    def __init__(self, window=None):
        super(Version20231231230000, self).__init__(window)
        self.window = window

    def up(self, conn):
        conn.execute(text("""
        ALTER TABLE ctx_item ADD COLUMN is_internal BOOLEAN NOT NULL DEFAULT 0 CHECK (is_internal IN (0, 1));
        """))
