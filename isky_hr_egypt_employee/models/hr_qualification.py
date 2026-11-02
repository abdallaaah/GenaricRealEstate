# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HrQualification(models.Model):
    _name = 'exp.hr.qualification'
    _description = 'Hr Qualification'

    name = fields.Char(string='Qualification Title',
                       required=True, translate=True)
    sequence = fields.Integer(
        'Sequence', default=1, help="Gives the sequence order when displaying a list of degrees.")

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Qualification must be unique!'),
    ]
