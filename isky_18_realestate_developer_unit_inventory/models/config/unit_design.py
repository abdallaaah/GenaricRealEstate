from odoo import fields, models


class UnitDesign(models.Model):
    _name = 'unit.design'

    name = fields.Char(string='Design Name', required=True)
    design_type = fields.Selection([
        ('modern', 'Modern'),
        ('classic', 'Classic'),
        ('contemporary', 'Contemporary')
    ], string='Design Type')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
