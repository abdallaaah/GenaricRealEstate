# -*- coding: utf-8 -*-

from odoo import fields, models


class WorkLocation(models.Model):
    _name = 'work.location'
    _description = 'Work Location'

    name = fields.Char(string="Name", required=False, translate=True)
    arabic_name = fields.Char(string="Arabic Name", translate=True)
