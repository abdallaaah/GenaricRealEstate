from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    # --- from arkzayed_18_realestate_development/models/account_move.py ---
    # Phase 3 step 2a: is_contract / is_collection / is_maintenance_collection are sales-owned
    # flags, not accounting fields, and moved to
    # isky_18_realestate_developer_sales_crm/models/core/account_move_crm_ext.py.
    # is_revenue_split_entry stays here - it marks a journal entry produced by the revenue-split
    # posting - but was renamed in Phase 3 step 2a to drop the two client entity names it used
    # to carry, per the Phase 7 rule against client names in field identifiers.
    is_revenue_split_entry = fields.Boolean(string="Is Revenue Split Entry", default=False)
    under_collection_date = fields.Date(string="Under Collection Date", copy=False)

    # Phase 2b: the cash-in-out statement feature (journal_type field,
    # action_cash_in_out_statement, and its is_receipt / _get_arabic_amount /
    # calculate_total_amount / get_currency_name helpers) moved to
    # arkzayed_18_gt_cheque_management, where its report action and template live. It had an
    # env.ref into that module while this bridge did not depend on it.

    # --- from arkzayed_18_realestate_development/models/account_invoice.py ---
    real_estate_ref = fields.Char("Real Estate Ref.")
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

    # action_register_penalty_payment moved to
    # isky_18_realestate_developer_sales_crm/models/core/account_move_crm_ext.py
    # (Phase 3 step 2b-a): it is gated by penalty_id and rendered by a sales_crm
    # view, and needs no bridge-owned field.


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.constrains('account_id', 'display_type')
    def _check_payable_receivable(self):
        """Override to skip validation for contract invoices"""
        for line in self:
            # Skip validation for contract invoices.
            # is_contract is sales-owned (declared in sales_crm as an _inherit on account.move),
            # so it is absent when this optional bridge runs without sales_crm. getattr keeps the
            # bridge installable and this validation correct on its own: with no sales module
            # there are no contract invoices to exempt.
            if getattr(line.move_id, 'is_contract', False):
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
