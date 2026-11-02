# -*- coding: utf-8 -*-
from odoo import models, fields, _


class PolicyGroup(models.Model):
    _name = 'policy.group'
    _description = 'Policy Group'

    name = fields.Char(string="Policy Group", required=1)
