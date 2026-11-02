# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ContractMedicalState(models.Model):
    _name = 'contract.medical.state'
    _description = 'Contract Medical State'

    name = fields.Char(string='Name', required=True, translate=True)
