from odoo import api, fields, models


class PermissionRequest(models.Model):
    _name = 'permission.request'
    _description = "Permission Request"
    _order = 'create_date desc'

    name = fields.Char(required=True, copy=False, readonly=True, default=lambda self: self.env._("New"))
    requester_id = fields.Many2one('res.users', default=lambda self: self.env.user, readonly=True)
    team_id = fields.Many2one('crm.team', related='requester_id.sale_team_id', store=True)
    request_type = fields.Selection([('lead', "Lead"), ('unit', "Unit")])
    client_name = fields.Char()
    client_number = fields.Char()
    approval_status = fields.Selection([
        ('pending', "Pending"), ('approved', "Approved"), ('rejected', "Rejected"),
    ], default='pending')
    request_details = fields.Text()
    operations_feedback = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', self.env._("New")) == self.env._("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code('permission.request')
        return super().create(vals_list)

    def action_approve(self):
        self.approval_status = 'approved'

    def action_reject(self):
        self.approval_status = 'rejected'
