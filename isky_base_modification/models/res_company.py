# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    name_ar = fields.Char(string="Arabic Name")
    cr_number = fields.Char(string="CR Number")
    po_box = fields.Char(string="P.O.Box")
    fax = fields.Char(string="Fax")
    mail_box = fields.Char(string='Mail Box')



