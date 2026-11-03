from odoo import fields, models


class RealEstateProjectPhase(models.Model):
    _name = 'real.estate.project.phase'

    name = fields.Char()
    image = fields.Image()
    project_id = fields.Many2one('realestate.project')
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    is_phase_one = fields.Boolean(default=False)
    is_phase_two = fields.Boolean(default=False)
    is_phase_three = fields.Boolean(default=False)
    is_phase_four = fields.Boolean(default=False)

