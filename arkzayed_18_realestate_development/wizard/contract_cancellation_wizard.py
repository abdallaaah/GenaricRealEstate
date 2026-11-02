from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ContractCancellationWizard(models.TransientModel):
    _name = 'contract.cancellation.wizard'
    _description = 'Contract Cancellation Wizard'

    sale_proposal_id = fields.Many2one('sale.proposal', string='Sale Proposal', required=True)
    cancellation_reason = fields.Text(string='Cancellation Reason', required=True)

    def action_confirm_cancellation(self):
        self.ensure_one()

        self.sale_proposal_id.write({
            'state': 'cancelled',
            'cancellation_reason': self.cancellation_reason,
            'cancelled_date': fields.Date.today(),
            'cancelled_by': self.env.user.id,
        })

        # Update unit status
        if self.sale_proposal_id.unit_id:
            cancel_reason = self.env['block.reason'].search([('blocked_from_cancellation', '=', True)], limit=1)
            if not cancel_reason:
                raise ValidationError(_("No block reason is configured for 'Blocked from Cancellation'. Please configure one in Block Reasons."))
            self.sale_proposal_id.unit_id.write({
                'unit_status': 'blocked',
                'reason_id': cancel_reason.id,
            })

        return {'type': 'ir.actions.act_window_close'}
