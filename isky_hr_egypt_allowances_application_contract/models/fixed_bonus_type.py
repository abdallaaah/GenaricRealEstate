# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class FixedBonusType(models.Model):
    _name = "fixed.bonus.type"
    _description = 'Fixed Bouns Type'

    name = fields.Char(string="Name", required=True)
