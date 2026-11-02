# -*- coding: utf-8 -*-

from odoo import models, fields


class ResPartner(models.Model):
    _inherit = "res.partner"

    mail_box = fields.Char(string='Mail Box')
    home_phone = fields.Char(string='Home Phone')
