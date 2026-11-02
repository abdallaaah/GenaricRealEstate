from odoo import models, fields, api
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class ProjectCommission(models.Model):
    _name = "project.commission"
    _description = "Project Commission"
    _rec_name = "developer_project_id"

    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    commission_percentage = fields.Float(string="Commission Base Percentage", required=True)
    additional_commission_percentage = fields.Float(string="Additional Percentage")
    developer_project_id = fields.Many2one('developer.project', string="Developer Project", required=True)
    is_first_commission = fields.Boolean(compute="_compute_is_first_commission", store=True,default=True)

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            # raise ValidationError if either start_date or end_date is not set
            if not record.start_date or not record.end_date:
                raise ValidationError("Both start date and end date must be set.")
            # Check if start_date is before end_date
            if record.start_date and record.end_date and record.start_date >= record.end_date:
                raise ValidationError("Start date must be before(less than) end date.")

            # Check if start_date is after the last commission's end_date
            if record.developer_project_id:
                last_commission = self.search([
                    ('developer_project_id', '=', record.developer_project_id.id),
                    ('id', '!=', record.id)
                ], order='end_date desc', limit=1)
                if last_commission and (record.start_date <= last_commission.end_date):
                    raise ValidationError(
                        f"The start date must be greater than the last end date which is {last_commission.end_date} for the same developer project."
                    )

    @api.depends('developer_project_id')
    def _compute_is_first_commission(self):
        """
        This compute method determines if the current commission record is the first one for the selected developer project.
        It sets is_first_commission to True if there are no other commission records for the same developer_project_id (excluding itself),
        and False otherwise. This ensures the field always reflects the current state, even if commissions are added or deleted.
        """
        for record in self:
            if record.developer_project_id:
                commission_count = self.search_count([
                    ('developer_project_id', '=', record.developer_project_id.id),
                    ('id', '!=', record.id)
                ])
                record.is_first_commission = commission_count == 0
            else:
                record.is_first_commission = False


    @api.model
    def create(self, vals):
        # Get the developer_project_id from the values
        developer_project_id = vals.get('developer_project_id')
        if developer_project_id:
            # Search for the last commission for this developer project
            last_commission = self.search([
                ('developer_project_id', '=', developer_project_id)
            ], order='end_date desc', limit=1)
            if last_commission:
                # If there is a previous commission, set start_date to last end_date + 1 day
                if last_commission.end_date:
                    next_start_date = fields.Date.from_string(last_commission.end_date) + relativedelta(days=1)
                    vals['start_date'] = next_start_date
        return super(ProjectCommission, self).create(vals)

    @api.onchange('developer_project_id')
    def _onchange_developer_project_id(self):
        """
        When the developer_project_id is changed, if this is not the first commission, set start_date to the last commission's end_date + 1 day.
        """
        if self.developer_project_id:
            last_commission = self.search([
                ('developer_project_id', '=', self.developer_project_id.id),
                ('id', '!=', self.id)
            ], order='end_date desc', limit=1)
            if last_commission and last_commission.end_date:
                self.start_date = fields.Date.from_string(last_commission.end_date) + relativedelta(days=1)
