from odoo import models, fields
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Phase 3 step 2a: sales-owned flags, moved here from the L1 accounting bridge. They are set
    # by sales flows, not by accounting. The bridge still reads is_contract (to exempt contract
    # invoices from payable/receivable validation) but does so via getattr, so it stays
    # installable on its own.
    is_contract = fields.Boolean(string='Is Contract', default=False,
                                 help='Check if this invoice is related to a real estate contract')
    is_collection = fields.Boolean(string="Is Collection", default=False)
    is_maintenance_collection = fields.Boolean(string="Is Maintenance Collection", default=False)

    sale_proposal_id = fields.Many2one('sale.proposal', string='Sale Proposal', readonly=True)
    penalty_id = fields.Many2one('installment.penalty', string='Penalty', readonly=True)
    sale_reservation_id = fields.Many2one('real.estate.sale.reservation', string='Sale Reservation', readonly=True)
    line_id = fields.Many2one("loan.line", "Contract Line")
    installment_line_id = fields.Many2one("installment.lines", "Contract Line")
    installment_lines_line_id = fields.Many2one("maintenance.installment.lines", "Contract Line")
    revenue_share_id = fields.Many2one('revenue.share2', string="Revenue Share")
    revenue_share_type = fields.Selection([('rev1', 'Rev1'), ('rev2', 'Rev2')])

    def action_register_penalty_payment(self):
        """Phase 3 step 2b-a: moved here from the L1 accounting bridge. It is gated by
        penalty_id and rendered by this module's own view, both of which live here, and it
        touches only core fields (state) plus core account.payment.register - no bridge-owned
        field. Leaving it in the bridge made the view fail to validate in Mode B with
        "action_register_penalty_payment is not a valid action on account.move"."""
        self.ensure_one()
        if self.state != 'posted':
            raise UserError('Please post the journal entry before registering payment.')
        return {
            'name': 'Register Payment',
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment.register',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'account.move',
                'active_ids': [self.id],
            },
        }
