#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://github.com/otectus/nexus_client                         #
# GitHub:  https://github.com/otectus/nexus_client   #
# MIT License                                        #
# Created By  : Otectus                  #
# Updated Date: 2024.01.06 04:00:00                  #
# ================================================== #

from sqlalchemy import text

from .base import BaseMigration


class Version20240106060000(BaseMigration):
    def __init__(self, window=None):
        super(Version20240106060000, self).__init__(window)
        self.window = window

    def up(self, conn):
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS calendar_note (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idx INTEGER,
            uuid TEXT,
            year INTEGER,
            month INTEGER,
            day INTEGER,
            status INTEGER,
            created_ts INTEGER,
            updated_ts INTEGER,
            title TEXT,
            content TEXT,
            is_important BOOLEAN NOT NULL CHECK (is_deleted IN (0, 1)),
            is_deleted BOOLEAN NOT NULL CHECK (is_deleted IN (0, 1))
        );"""))
