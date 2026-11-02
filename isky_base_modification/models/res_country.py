# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCountry(models.Model):
    _inherit = 'res.country'

    is_egypt = fields.Boolean(string='Egypt ??')
    nationality = fields.Char(string='Nationality', translate=True)
    is_saudi_arabia = fields.Boolean(string='Saudi Arabia')
