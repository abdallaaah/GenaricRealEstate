from odoo import api, fields, models
from odoo.exceptions import AccessError


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
        self._check_can_decide()
        self.with_context(permission_request_decision=True).write({'approval_status': 'approved'})

    def action_reject(self):
        self._check_can_decide()
        self.with_context(permission_request_decision=True).write({'approval_status': 'rejected'})

    def _check_can_decide(self):
        """D9: deciding a request takes the approver group, and never on your own request --
        holding the group does not exempt the requester from the second rule."""
        if self.env.su:
            return
        if not self.env.user.has_group('isky_20_broker_base.group_permission_approver'):
            raise AccessError(self.env._(
                "Only a Permission Request Approver can approve or reject requests."))
        for request in self:
            if request.requester_id == self.env.user:
                raise AccessError(self.env._(
                    "You cannot decide your own permission request (%s).", request.name))

    def write(self, vals):
        # approval_status moves only through action_approve/action_reject (which stamp the
        # context after their checks); a direct write would bypass both the group and the
        # not-your-own-request rule.
        if ('approval_status' in vals and not self.env.su
                and not self.env.context.get('permission_request_decision')):
            raise AccessError(self.env._(
                "The approval status changes only through the Approve and Reject buttons."))
        return super().write(vals)
