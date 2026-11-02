# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class CardType(models.Model):
    _name = 'card.type'
    _description = 'Card Type'

    name = fields.Char(string='Name', required=True, translate=True)


class LicenceDegree(models.Model):
    _name = 'licence.degree'
    _description = 'License Degree'

    name = fields.Char(string='Name', required=True, translate=True)
