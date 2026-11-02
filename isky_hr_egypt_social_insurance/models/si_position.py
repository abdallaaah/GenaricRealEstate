# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SiPosition(models.Model):
    _name = 'si.position'
    _description = 'SI Position'

    name = fields.Char(string='Name', translate=True)
