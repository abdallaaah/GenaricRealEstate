# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class VisaType(models.Model):
    _name = "visa.type"
    _description = 'Visa Type'

    name = fields.Char(string='Type', required=1, translate=True)
