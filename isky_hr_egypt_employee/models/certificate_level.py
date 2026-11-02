# -*- coding: utf-8 -*-
from odoo import models, fields, api


class CertificateLevel(models.Model):
    _name = 'certificate.level'
    _description = 'Certificate Level'

    name = fields.Char(string='Name', required=True, translate=True)
