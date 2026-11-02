# -*- coding: utf-8 -*-
from odoo import models


class SaleProposal(models.Model):
    _name = 'sale.proposal'
    _inherit = ['sale.proposal', 'template.document.mixin']
