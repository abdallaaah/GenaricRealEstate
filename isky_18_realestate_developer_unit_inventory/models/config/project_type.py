from odoo import fields, models


class RealEstateProjectType(models.Model):
    """Specify real estate project type"""

    _name = 'realestate.project.type'
    _rec_name = 'project_type'

    project_type = fields.Selection([('residential', 'Residential'), ('commercial', 'Commercial'),
                                     ('administrative', 'Administrative'), ('industrial', 'Industrial'),
                                     ('medical', 'Medical'), ('entertainment', 'Entertainment')], string='Type')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
