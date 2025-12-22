#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2024.05.01 03:00:00                  #
# ================================================== #

from sqlalchemy import text

from .base import BaseMigration


class Version20240501030000(BaseMigration):
    def __init__(self, window=None):
        super(Version20240501030000, self).__init__(window)
        self.window = window

    def up(self, conn):
        conn.execute(text("""
        ALTER TABLE ctx_meta ADD COLUMN root_id INTEGER;
        """))
        conn.execute(text("""
        ALTER TABLE ctx_meta ADD COLUMN parent_id INTEGER;
        """))
        conn.execute(text("""
        ALTER TABLE ctx_meta ADD COLUMN owner_uuid TEXT;
        """))
