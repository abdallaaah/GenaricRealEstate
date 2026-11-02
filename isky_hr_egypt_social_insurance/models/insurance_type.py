# -*- coding: utf-8 -*-

from odoo import models, fields, api


class InsuranceType(models.Model):
    _name = 'insurance.type'
    _description = 'Insurance Type'

    name = fields.Char(string="Name", required=True, translate=True)
