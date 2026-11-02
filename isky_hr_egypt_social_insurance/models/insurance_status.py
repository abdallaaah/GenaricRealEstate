# -*- coding: utf-8 -*-

from odoo import models, fields, api


class InsuranceStatus(models.Model):
    _name = 'insurance.status'
    _description = 'Insurance Status'

    name = fields.Char(string="Name", required=True, translate=True)
