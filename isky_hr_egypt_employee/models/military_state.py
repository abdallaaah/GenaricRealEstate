# -*- coding: utf-8 -*-
from odoo import models, fields, api


class MilitaryState(models.Model):
    _name = 'military.state'
    _description = 'Military State'

    name = fields.Char(string='Name', required=True, translate=True)
