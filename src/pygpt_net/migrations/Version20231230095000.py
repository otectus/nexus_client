#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2023.12.30 09:00:00                  #
# ================================================== #

from sqlalchemy import text

from .base import BaseMigration


class Version20231230095000(BaseMigration):
    def __init__(self, window=None):
        super(Version20231230095000, self).__init__(window)
        self.window = window

    def up(self, conn):
        conn.execute(text("""
        ALTER TABLE notepad ADD COLUMN is_initialized BOOLEAN NOT NULL DEFAULT 0 CHECK (is_initialized IN (0, 1));
        """))
