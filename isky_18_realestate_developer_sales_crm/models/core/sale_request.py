from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class SaleRequest(models.Model):
    _name = 'sale.request'
    _description = 'Request Sale'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True,
                        default=lambda self: _('New'))
    requester_id = fields.Many2one('res.users', string='Requester',
                                    default=lambda self: self.env.user, readonly=True, tracking=True)
    unit_id = fields.Many2one('real.estate.unit', string='Unit', required=True, tracking=True,
                               domain=[('unit_status', '=', 'available_for_sale')])
    unit_area = fields.Float(related='unit_id.unit_area', string='Unit Area', store=True, readonly=True)
    total_price_unit = fields.Float(related='unit_id.total_price_unit', string='Unit Total Price',
                                     store=True, readonly=True)
    reason_id = fields.Many2one('block.reason', string='Block Reason', required=True, tracking=True,
                                 domain=[('for_sale_request', '=', True)])
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, copy=False)
    rejection_reason = fields.Text(string='Rejection Reason')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.request') or _('New')
        return super().create(vals_list)

    def action_submit(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_("Only draft requests can be submitted."))
            record.state = 'submitted'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Request Submitted'),
                'message': _(
                    "Your sale request has been submitted for approval. Please note that the "
                    "unit is not blocked until Operations accepts the request."
                ),
                'type': 'success',
                'sticky': True,
            }
        }

    def action_cancel(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_("Only draft requests can be cancelled."))
            record.state = 'cancelled'

    def _check_approval_rights(self):
        if not self.env.user.has_group('arkzayed_18_realestate_development.group_block_unit'):
            raise ValidationError(_("You do not have the permission to accept or reject sale requests."))

    def action_accept(self):
        self._check_approval_rights()
        for record in self:
            if record.state != 'submitted':
                raise UserError(_("Only submitted requests can be accepted."))
            if record.unit_id.unit_status != 'available_for_sale':
                raise UserError(_(
                    "Unit %(unit)s is no longer Available For Sale (current status: %(status)s). "
                    "This request can no longer be accepted.",
                    unit=record.unit_id.display_name,
                    status=dict(record.unit_id._fields['unit_status'].selection).get(record.unit_id.unit_status),
                ))

            record.unit_id.write({
                'reason_id': record.reason_id.id,
                'unit_status': 'blocked',
            })
            record.unit_id.message_post(
                body=_("Blocked via Sale Request %(name)s — Reason: %(reason)s",
                       name=record.name, reason=record.reason_id.name),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
            record.state = 'accepted'

    def action_reject(self):
        self._check_approval_rights()
        for record in self:
            if record.state != 'submitted':
                raise UserError(_("Only submitted requests can be rejected."))
            record.state = 'rejected'

    def action_print_unit_offer_plan(self):
        self.ensure_one()
        if not self.unit_id:
            raise UserError(_("No unit selected for this request."))
        return self.unit_id.action_print_unit_offer_plan()
