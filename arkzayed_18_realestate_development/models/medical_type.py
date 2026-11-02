from odoo import fields, models


class MedicalType(models.Model):
    _name = "medical.type"
    _description = "Medical Type"

    name = fields.Char(string="Medical Type", required=True)

