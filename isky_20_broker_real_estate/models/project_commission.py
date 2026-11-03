from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProjectCommission(models.Model):
    _name = 'project.commission'
    _description = "Project Commission"
    _rec_name = 'developer_project_id'
    _order = 'developer_project_id, start_date'

    developer_project_id = fields.Many2one('developer.project', required=True, ondelete='cascade')
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    commission_percentage = fields.Float(string="Commission Base Percentage", required=True)
    additional_commission_percentage = fields.Float(string="Additional Percentage")
    # Replaces the v17 developer.project.double_commission/half_commission booleans: the
    # multiplier is now a property of the dated commission rule, so it can vary per period
    # instead of being a permanent flag on the whole project.
    commission_multiplier = fields.Selection([
        ('normal', "Normal"),
        ('half', "Half"),
        ('double', "Double"),
    ], default='normal', required=True)
    is_first_commission = fields.Boolean(compute='_compute_is_first_commission', store=True)

    @api.depends('developer_project_id')
    def _compute_is_first_commission(self):
        for commission in self:
            if not commission.developer_project_id:
                commission.is_first_commission = False
                continue
            earlier_count = self.search_count([
                ('developer_project_id', '=', commission.developer_project_id.id),
                ('id', '!=', commission.id),
            ])
            commission.is_first_commission = earlier_count == 0

    @api.constrains('start_date', 'end_date', 'developer_project_id')
    def _check_dates(self):
        for commission in self:
            if commission.start_date >= commission.end_date:
                raise ValidationError(self.env._("Start date must be before end date."))
            previous = self.search([
                ('developer_project_id', '=', commission.developer_project_id.id),
                ('id', '!=', commission.id),
            ], order='end_date desc', limit=1)
            if previous and commission.start_date <= previous.end_date:
                raise ValidationError(self.env._(
                    "The start date must be after the previous commission's end date (%s) for this project.",
                    previous.end_date,
                ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            developer_project_id = vals.get('developer_project_id')
            if developer_project_id and not vals.get('start_date'):
                previous = self.search([
                    ('developer_project_id', '=', developer_project_id),
                ], order='end_date desc', limit=1)
                if previous and previous.end_date:
                    vals['start_date'] = fields.Date.add(previous.end_date, days=1)
        return super().create(vals_list)

    @api.onchange('developer_project_id')
    def _onchange_developer_project_id(self):
        if self.developer_project_id:
            previous = self.search([
                ('developer_project_id', '=', self.developer_project_id.id),
                ('id', '!=', self.id),
            ], order='end_date desc', limit=1)
            if previous and previous.end_date:
                self.start_date = fields.Date.add(previous.end_date, days=1)
