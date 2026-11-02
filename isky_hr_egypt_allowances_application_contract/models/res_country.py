# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ResCountry(models.Model):
    _inherit = 'res.country'

    is_egypt = fields.Boolean(string='Egypt ??')
    nationality = fields.Char(string='Nationality', translate=True)
