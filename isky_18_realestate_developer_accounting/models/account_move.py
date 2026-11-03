from num2words import num2words

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    # --- from arkzayed_18_realestate_development/models/account_move.py ---
    is_contract = fields.Boolean(string='Is Contract', default=False,
                                 help='Check if this invoice is related to a real estate contract')
    sale_proposal_id = fields.Many2one('sale.proposal', string='Sale Proposal', readonly=True)
    penalty_id = fields.Many2one('installment.penalty', string='Penalty', readonly=True)
    sale_reservation_id = fields.Many2one('real.estate.sale.reservation', string='Sale Reservation', readonly=True)
    is_collection = fields.Boolean(string="Is Collection", default=False)
    is_maintenance_collection = fields.Boolean(string="Is Maintenance Collection", default=False)
    is_gis_quia = fields.Boolean(string="Is GIS/OAYA", default=False)
    under_collection_date = fields.Date(string="Under Collection Date", copy=False)

    # --- from arkzayed_18_gt_cheque_management/models/account_move.py (not actually cheque-specific;
    # this file was not even imported by that module's __init__.py, so it was dead code there) ---
    journal_type = fields.Selection(
        related='journal_id.type',
        string='Journal Type',
        store=True,
        readonly=True
    )

    # --- from arkzayed_18_realestate_development/models/account_invoice.py ---
    real_estate_ref = fields.Char("Real Estate Ref.")
    line_id = fields.Many2one("loan.line", "Contract Line")
    installment_line_id = fields.Many2one("installment.lines", "Contract Line")
    installment_lines_line_id = fields.Many2one("maintenance.installment.lines", "Contract Line")
    revenue_share_id = fields.Many2one('revenue.share2', string="Revenue Share")
    revenue_share_type = fields.Selection([('rev1', 'Rev1'), ('rev2', 'Rev2')])
    entry_sequence = fields.Char(readonly=True, copy=False)
    is_checked = fields.Selection([
        ('checked', 'Checked'),
        ('not_checked', 'Not Checked')
    ], string="Checked", default='not_checked', compute='_compute_is_checked', store=True)
    checked_bool = fields.Boolean(string="Checked", default=False)

    @api.depends('checked_bool')
    def _compute_is_checked(self):
        for record in self:
            record.is_checked = 'checked' if record.checked_bool else 'not_checked'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('company_id'):
                vals['company_id'] = self.env.company.id
        res = super(AccountMove, self).create(vals_list)
        res.entry_sequence = self.env['ir.sequence'].next_by_code('entry.sequence')
        return res

    def action_cash_in_out_statement(self):
        return self.env.ref('arkzayed_18_gt_cheque_management.account_cash_in_out_report').report_action(self)

    def is_receipt(self):
        """
        Check if the move is a receipt based on the journal type.

        :return: True if the journal type is 'bank_receipt', otherwise False.
        """
        for line in self.line_ids:
            if line.account_id.account_type == 'asset_cash':
                return line.amount_currency >= 0

    def _get_arabic_amount(self, amount, lang):
        return num2words(float(abs(amount)), lang=lang)

    def calculate_total_amount(self):
        """
        Calculate the total amount_currency for lines with account_type 'asset_cash'.

        :return: The total amount_currency for 'asset_cash' account type.
        """
        total_amount = 0
        for line in self.line_ids:
            if line.account_id.account_type == 'asset_cash':
                total_amount += abs(line.amount_currency)
        return total_amount

    def get_currency_name(self):
        """
        Retrieve the currency name for lines with account_type 'asset_cash'.

        :return: The currency name if found, otherwise None.
        """
        if self.line_ids:
            for line in self.line_ids:
                if line.account_id.account_type == 'asset_cash' and line.currency_id:
                    return line.currency_id.name
        return None

    def action_register_penalty_payment(self):
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


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # --- from arkzayed_cost_distribution/models/account_move_line.py ---
    distribution_state = fields.Selection([
        ('pending', 'Not Distributed'),
        ('partial', 'Partially Distributed'),
        ('done', 'Fully Distributed'),
    ], string='Unit Distribution', default='pending')

    allocation_ids = fields.One2many('arkzayed.cost.allocation', 'move_line_id', string='Cost Allocations')

    distributed_amount = fields.Monetary(compute='_compute_distributed_amount', string='Distributed Amount')

    remaining_amount = fields.Monetary(compute='_compute_distributed_amount', string='Remaining to Distribute')

    @api.constrains('account_id', 'display_type')
    def _check_payable_receivable(self):
        """Override to skip validation for contract invoices"""
        for line in self:
            # Skip validation for contract invoices
            if line.move_id.is_contract:
                continue

            # Original validation for non-contract moves
            account_type = line.account_id.account_type
            if line.move_id.is_sale_document(include_receipts=True):
                if account_type == 'liability_payable':
                    raise UserError(
                        _("Account %s is of payable type, but is used in a sale operation.", line.account_id.code))
                if (line.display_type == 'payment_term') ^ (account_type == 'asset_receivable'):
                    raise UserError(_("Any journal item on a receivable account must have a due date and vice versa."))
            if line.move_id.is_purchase_document(include_receipts=True):
                if account_type == 'asset_receivable':
                    raise UserError(_("Account %s is of receivable type, but is used in a purchase operation.",
                                      line.account_id.code))
                if (line.display_type == 'payment_term') ^ (account_type == 'liability_payable'):
                    raise UserError(_("Any journal item on a payable account must have a due date and vice versa."))

    @api.depends('allocation_ids.amount', 'price_total')
    def _compute_distributed_amount(self):
        for line in self:
            distributed = sum(line.allocation_ids.mapped('amount'))
            line.distributed_amount = distributed
            # The distributable amount is the line total including taxes.
            line.remaining_amount = line.price_total - distributed

    def action_open_cost_distribution_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Distribute Cost to Units',
            'res_model': 'arkzayed.cost.distribution.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_move_line_id': self.id},
        }
