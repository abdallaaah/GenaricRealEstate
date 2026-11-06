# -*- coding: utf-8 -*-
from num2words import num2words

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    real_estate_ref = fields.Char("Real Estate Ref.")

    # --- from arkzayed_18_gt_cheque_management/models/account_payment.py (not actually cheque-specific) ---
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user)
    is_credit_card = fields.Boolean(string="Credit Card")
    card_number = fields.Char()
    credit_bank_id = fields.Many2one('res.bank', string='Bank')
    amount_in_words = fields.Char(compute="_compute_amount_in_words")

    @api.depends('amount')
    def _compute_amount_in_words(self):
        for payment in self:
            if payment.amount:
                amount_in_words = num2words(payment.amount, lang='ar', to='currency',
                                                 currency='EGP')
                payment.amount_in_words = amount_in_words + ' فقط '
            else:
                payment.amount_in_words = False

    def _get_arabic_amount(self, amount, lang):
        return num2words(float(amount), lang=lang)

    @api.depends('price_after_discount')
    def _compute_unit_price_words(self):
        # NOTE: dead code inherited as-is — price_after_discount/unit_price_words don't exist
        # on account.payment and this compute isn't attached to any field, so it never runs.
        for rec in self:
            if rec.price_after_discount:
                rec.unit_price_words = num2words(rec.price_after_discount, lang='ar', to='currency',
                                                 currency='EGP')
            else:
                rec.unit_price_words = False

    is_refund = fields.Boolean()
    payment_method_type = fields.Selection([
        ('cash', 'Cash'),
        ('bank', 'Bank'),
        ('cheque', 'Cheque')
    ], string='Payment Method Type')
    installment_date = fields.Date(string='Installment Date', help='Date of the installment payment')
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        readonly=False,
        required=True,
        check_company=True,
        domain="[('id', 'in', suitable_journal_ids)]",
    )

    # Phase 3 step 2a: is_down_payment is a sales-owned flag and moved to
    # isky_18_realestate_developer_sales_crm/models/core/account_payment.py. The down-payment
    # ACCOUNT SELECTION below is accounting behaviour and stays here; it reads the flag via
    # getattr so this optional bridge still installs and behaves correctly without sales_crm
    # (no sales module => no down payments to redirect).
    is_pre_payment = fields.Boolean(string='Is Pre-Payment')

    is_overseas = fields.Boolean(
        string='Is Overseas Payment',
        default=False,
        help='Flag to indicate if this payment is from an overseas contract'
    )
    overseas_payment_type = fields.Selection([
        ('installment', 'Installment'),
        ('maintenance', 'Maintenance')
    ], string='Overseas Payment Type', help='Type of overseas payment for account determination')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_check', 'To Check'),
        ('cfo_approved', 'CFO Approved'),
        ('deputy_cfo_approved', 'Deputy CEO Approved'),
        ('in_process', 'In Process'),
        ('paid', 'Paid'),
        ('canceled', 'Cancelled'),
    ], default='draft', tracking=True)

    custom_exchange_rate = fields.Float(
        string='Exchange Rate',
        digits=(16, 6),
        help='Company currency per 1 unit of the payment currency. Defaults from the currency '
             'rate on the payment date and can be edited before the payment is posted.'
    )
    converted_amount = fields.Monetary(
        string='Amount after Conversion',
        compute='_compute_converted_amount',
        store=True,
        currency_field='company_currency_id',
        help='Amount in company currency, equal to Amount x Exchange Rate. This is the amount '
             'posted to the journal entry and used to pay the installment.'
    )

    @api.depends('amount', 'custom_exchange_rate')
    def _compute_converted_amount(self):
        for rec in self:
            rec.converted_amount = rec.amount * rec.custom_exchange_rate if rec.custom_exchange_rate else 0.0

    @api.onchange('currency_id', 'company_id')
    def _onchange_currency_id_exchange_rate(self):
        """Default the exchange rate from the currency rate on the payment date.
        Only applies when the payment currency differs from the company currency."""
        company_currency = self.company_id.currency_id
        if self.currency_id and company_currency and self.currency_id != company_currency:
            self.custom_exchange_rate = self.currency_id._convert(
                1.0, company_currency, self.company_id, self.date or fields.Date.context_today(self)
            )
        else:
            self.custom_exchange_rate = 0.0

    @api.depends('payment_type')
    def _compute_available_journal_ids(self):
        """
        Get all journals having at least one payment method for inbound/outbound depending on the payment_type.
        """
        payment_methods = self._context.get('payment_methods')

        if payment_methods is None:
            payment_methods = ('bank', 'cash')
        else:
            payment_methods = (payment_methods,)
        journals = self.env['account.journal'].search([
            '|',
            ('company_id', 'parent_of', self.env.company.id),
            ('company_id', 'child_of', self.env.company.id),
            ('type', 'in', payment_methods),
        ])
        for pay in self:
            if pay.payment_type == 'inbound':
                pay.available_journal_ids = journals.filtered('inbound_payment_method_line_ids')
            else:
                pay.available_journal_ids = journals.filtered('outbound_payment_method_line_ids')

    def _seek_for_lines(self):
        """Override to use down payment accounts when is_down_payment or is_pre_payment is True"""
        liquidity_lines, counterpart_lines, writeoff_lines = super(AccountPayment, self)._seek_for_lines()

        if self.partner_id:
            # Handle is_down_payment (sales-owned field; absent without sales_crm)
            if getattr(self, 'is_down_payment', False):
                for line in counterpart_lines:
                    if self.payment_type == 'inbound':
                        # For inbound payments (customer payments), use down payment receivable account
                        if line.account_id == self.partner_id.property_account_receivable_id:
                            if self.partner_id.property_account_down_payment_receivable_id:
                                line.account_id = self.partner_id.property_account_down_payment_receivable_id
                    elif self.payment_type == 'outbound':
                        # For outbound payments (refunds), also check if it's a customer refund
                        if line.account_id == self.partner_id.property_account_receivable_id:
                            # This is a customer refund, use down payment receivable account
                            if self.partner_id.property_account_down_payment_receivable_id:
                                line.account_id = self.partner_id.property_account_down_payment_receivable_id
                        elif line.account_id == self.partner_id.property_account_payable_id:
                            # This is a vendor payment, use down payment payable account
                            if self.partner_id.property_account_down_payment_payable_id:
                                line.account_id = self.partner_id.property_account_down_payment_payable_id

            # Handle is_pre_payment - specifically for outbound payments using payable account
            if self.is_pre_payment:
                for line in counterpart_lines:
                    if self.payment_type == 'outbound':
                        # For outbound payments (sent payments), use down payment payable account
                        if line.account_id == self.partner_id.property_account_payable_id:
                            if self.partner_id.property_account_down_payment_payable_id:
                                line.account_id = self.partner_id.property_account_down_payment_payable_id

        return liquidity_lines, counterpart_lines, writeoff_lines

    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None, **kwargs):
        """Override to use overseas accounts when is_overseas is True, and to book the
        journal entry at the user-edited exchange rate instead of the automatic currency
        rate, when one was set (custom_exchange_rate). amount_currency on the lines keeps
        the original foreign-currency amount either way."""
        if force_balance is None and self.custom_exchange_rate and self.currency_id != self.company_currency_id:
            force_balance = abs(self.converted_amount)

        line_vals_list = super(AccountPayment, self)._prepare_move_line_default_vals(
            write_off_line_vals=write_off_line_vals,
            force_balance=force_balance,
            **kwargs
        )

        # Handle overseas payments
        if self.is_overseas and self.overseas_payment_type:
            # Get overseas accounts from settings
            ICP = self.env['ir.config_parameter'].sudo()

            if self.overseas_payment_type == 'installment':
                overseas_account_id = ICP.get_param('arkzayed_18_realestate_development.overseas_installment_account')
            elif self.overseas_payment_type == 'maintenance':
                overseas_account_id = ICP.get_param('arkzayed_18_realestate_development.overseas_maintenance_account')
            else:
                overseas_account_id = None

            if overseas_account_id:
                overseas_account_id = int(overseas_account_id)

                # Replace the receivable account with overseas account
                for line_vals in line_vals_list:
                    # Find the credit line (receivable account for inbound payments)
                    if self.payment_type == 'inbound':
                        if line_vals.get('account_id') == self.partner_id.property_account_receivable_id.id:
                            line_vals['account_id'] = overseas_account_id

        # Handle is_down_payment (sales-owned field; absent without sales_crm)
        if self.partner_id:
            if getattr(self, 'is_down_payment', False):
                for line_vals in line_vals_list:
                    if self.payment_type == 'inbound':
                        if line_vals.get('account_id') == self.partner_id.property_account_receivable_id.id:
                            if self.partner_id.property_account_down_payment_receivable_id:
                                line_vals['account_id'] = self.partner_id.property_account_down_payment_receivable_id.id
                    elif self.payment_type == 'outbound':
                        if line_vals.get('account_id') == self.partner_id.property_account_receivable_id.id:
                            if self.partner_id.property_account_down_payment_receivable_id:
                                line_vals['account_id'] = self.partner_id.property_account_down_payment_receivable_id.id
                        elif line_vals.get('account_id') == self.partner_id.property_account_payable_id.id:
                            if self.partner_id.property_account_down_payment_payable_id:
                                line_vals['account_id'] = self.partner_id.property_account_down_payment_payable_id.id

            if self.is_pre_payment:
                for line_vals in line_vals_list:
                    if self.payment_type == 'outbound':
                        if line_vals.get('account_id') == self.partner_id.property_account_payable_id.id:
                            if self.partner_id.property_account_down_payment_payable_id:
                                line_vals['account_id'] = self.partner_id.property_account_down_payment_payable_id.id

        return line_vals_list

    def action_to_check(self):
        for payment in self:
            if payment.state != 'draft':
                raise ValidationError("Only Draft payments can be sent to Check.")
            payment._check_down_payment_accounts()
            payment.state = 'to_check'

    def action_cfo_approval(self):
        for payment in self:
            if payment.state != 'to_check':
                raise ValidationError("Only To Check payments can be approved by CFO.")
            payment.state = 'cfo_approved'

    def action_deputy_cfo_approval(self):
        for payment in self:
            if payment.state != 'cfo_approved':
                raise ValidationError("Only CFO Approved payments can be approved by Deputy CFO.")
            payment.state = 'deputy_cfo_approved'

    def _check_down_payment_accounts(self):
        for rec in self:
            if getattr(rec, 'is_down_payment', False) and not rec.partner_id.property_account_down_payment_receivable_id:
                raise ValidationError(_("Please set 'Account Down Payment Receivable' for partner %s") % rec.partner_id.name)
            if rec.is_pre_payment and not rec.partner_id.property_account_down_payment_payable_id:
                raise ValidationError(_("Please set 'Account Down Payment Payable' for partner %s") % rec.partner_id.name)

    @api.constrains('state', 'move_id')
    def _check_move_id(self):
        for payment in self:
            if (
                    payment.state not in ('draft', 'to_check','cfo_approved','deputy_cfo_approved', 'canceled')
                    and not payment.move_id
                    and payment.outstanding_account_id
            ):
                raise ValidationError(
                    _("A payment with an outstanding account cannot be confirmed without having a journal entry."))
