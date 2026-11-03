# -*- coding: utf-8 -*-
from num2words import num2words

from odoo.addons.arkzayed_18_realestate_development.models.selections import contract_type_selection
from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError, ValidationError


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

    sale_reservation_id = fields.Many2one("real.estate.sale.reservation", "Sale Reservation")
    from_down_payment = fields.Boolean()
    sale_proposal_id = fields.Many2one("sale.proposal", "Sale Proposal")
    loan_line_id = fields.Many2one("loan.line", "Loan Line")
    eoi_id = fields.Many2one('eoi.eoi', 'EOI', domain=[('status', '=', 'new')])
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

    is_down_payment = fields.Boolean()
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

    installment_line_id = fields.Many2one('installment.lines')
    maintenance_installment_line_id = fields.Many2one('maintenance.installment.lines', string='Maintenance Installment')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('to_check', 'To Check'),
        ('cfo_approved', 'CFO Approved'),
        ('deputy_cfo_approved', 'Deputy CEO Approved'),
        ('in_process', 'In Process'),
        ('paid', 'Paid'),
        ('canceled', 'Cancelled'),
    ], default='draft', tracking=True)

    unit_id = fields.Many2one(
        'real.estate.unit',
        string='Unit',
        copy=False,
        tracking=True,
        compute='_compute_unit_id',
        store=True,
    )

    collection_move_ids = fields.Many2many(
        'account.move',
        string='Collection Journal Entry',
        readonly=True,
        copy=False
    )
    collection_entry_count = fields.Integer(
        string='Collection Entries',
        compute='_compute_collection_entry_count'
    )
    contract_type = fields.Selection(
        selection=contract_type_selection,
        string="Contract Type",
        compute="_compute_contract_type",
        store=True,
    )
    reservation_payment_id = fields.Many2one('reservation.payment')
    eoi_payment_id = fields.Many2one('eoi.payment')

    allocation_ids = fields.One2many('payment.allocation', 'payment_id', string='Allocations')
    unallocated_amount = fields.Float(string='Unallocated Balance', compute='_compute_unallocated', store=True)

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

    from_eoi = fields.Boolean(string='Related To EOI', default=False, help='Indicates if the payment is created from an EOI', copy=False)
    from_reservation = fields.Boolean(string='Related To Reservation', default=False, copy=False)
    from_contract = fields.Boolean(string='Related To Contract', default=False, copy=False)
    is_commission_payment = fields.Boolean(
        string='Is Commission Payment',
        default=False,
        copy=False,
        help='Payment created from a broker/sales commission claim; not tied to installments so allocation is not required.'
    )

    available_installment_ids = fields.Many2many(
        'installment.lines',
        compute='_compute_available_allocations',
        string='Available Installments'
    )
    available_maintenance_ids = fields.Many2many(
        'maintenance.installment.lines',
        compute='_compute_available_allocations',
        string='Available Maintenance'
    )
    realestate_related_seq = fields.Char(string='Realestate Related Sequence', copy=False)

    # A single customer payment may settle installments of several of the payer's
    # contracts. sale_proposal_id stays the MAIN contract; these are the extra ones.
    additional_proposal_ids = fields.Many2many(
        'sale.proposal',
        'account_payment_additional_proposal_rel',
        'payment_id', 'proposal_id',
        string='Additional Contracts',
        copy=False,
    )
    additional_unit_ids = fields.Many2many(
        'real.estate.unit',
        'account_payment_additional_unit_rel',
        'payment_id', 'unit_id',
        string='Additional Units',
        compute='_compute_additional_unit_ids',
        inverse='_inverse_additional_unit_ids',
        store=True,
    )

    @api.depends('additional_proposal_ids', 'additional_proposal_ids.unit_id')
    def _compute_additional_unit_ids(self):
        for rec in self:
            rec.additional_unit_ids = rec.additional_proposal_ids.mapped('unit_id')

    def _inverse_additional_unit_ids(self):
        """Keep additional_proposal_ids in sync when units are set directly.
        A unit belongs to exactly one contract (unit.sale_contract_id)."""
        for rec in self:
            proposals = rec.env['sale.proposal']
            for unit in rec.additional_unit_ids:
                contract = unit.sale_contract_id
                if not contract:
                    raise ValidationError(
                        _("The unit '%s' is not linked to any contract.") % unit.display_name)
                proposals |= contract
            rec.additional_proposal_ids = proposals

    @api.onchange('additional_unit_ids')
    def _onchange_additional_unit_ids(self):
        """Picking an additional unit fills the matching contract.
        In onchange the units are NewId records, so resolve the real record first."""
        proposals = self.env['sale.proposal']
        for unit in self.additional_unit_ids:
            real_unit = unit._origin or unit
            contract = real_unit.sale_contract_id
            if not contract:
                raise ValidationError(
                    _("The unit '%s' is not linked to any contract.") % real_unit.display_name)
            proposals |= contract
        self.additional_proposal_ids = proposals

    @api.constrains('additional_proposal_ids', 'sale_proposal_id', 'partner_id')
    def _check_additional_proposals(self):
        for rec in self:
            if not rec.additional_proposal_ids:
                continue
            if not rec.sale_proposal_id:
                raise ValidationError(
                    _("Please set the main Sale Proposal before adding additional contracts."))
            if rec.sale_proposal_id in rec.additional_proposal_ids:
                raise ValidationError(
                    _("The main contract (%s) cannot also be listed as an additional contract.")
                    % rec.sale_proposal_id.name)
            wrong = rec.additional_proposal_ids.filtered(lambda p: p.customer_id != rec.partner_id)
            if wrong:
                raise ValidationError(_(
                    "These additional contracts do not belong to the payer (%(payer)s): %(contracts)s",
                    payer=rec.partner_id.display_name or '',
                    contracts=', '.join(wrong.mapped('name')),
                ))

    @api.depends(
        'sale_proposal_id', 'additional_proposal_ids', 'sale_reservation_id',
        'allocation_ids.installment_id', 'allocation_ids.maintenance_id'
    )
    def _compute_available_allocations(self):
        for rec in self:
            proposals = rec.sale_proposal_id | rec.additional_proposal_ids
            reservation = rec.sale_reservation_id

            all_inst = proposals.mapped('installment_ids') | \
                       (reservation.installment_ids if reservation else self.env['installment.lines'])
            all_maint = proposals.mapped('maintenance_installment_ids') | \
                        (reservation.maintenance_installment_ids if reservation else self.env[
                            'maintenance.installment.lines'])

            # Unpaid lines
            unpaid_inst = all_inst.filtered(lambda l: l.remaining_amount > 0)
            unpaid_maint = all_maint.filtered(lambda l: l.remaining_amount > 0)

            # Lines already selected in allocation table
            selected_inst = rec.allocation_ids.mapped('installment_id')
            selected_maint = rec.allocation_ids.mapped('maintenance_id')

            # Filter out selected lines from dropdown options
            rec.available_installment_ids = unpaid_inst - selected_inst
            rec.available_maintenance_ids = unpaid_maint - selected_maint

    @api.depends('amount', 'currency_id', 'date', 'company_id', 'allocation_ids.allocated_amount',
                 'custom_exchange_rate', 'converted_amount')
    def _compute_unallocated(self):
        for rec in self:
            total_allocated = sum(rec.allocation_ids.mapped('allocated_amount'))
            rec.unallocated_amount = max(0.0, rec._get_amount_company_currency() - total_allocated)

    def _get_amount_company_currency(self):
        """allocated_amount on payment.allocation is always expressed in the company
        currency (it mirrors installment.lines.remaining_amount, itself tied to
        company_id.currency_id). A payment can be registered in another currency
        (e.g. USD), so convert its amount before comparing it to allocations."""
        self.ensure_one()
        company_currency = self.company_id.currency_id
        if self.currency_id == company_currency:
            return self.amount
        if self.custom_exchange_rate:
            return self.converted_amount
        return self.currency_id._convert(
            self.amount, company_currency, self.company_id, self.date or fields.Date.context_today(self)
        )

    @api.depends(
        'installment_line_id.sale_proposal_id.contract_type',
        'maintenance_installment_line_id.sale_proposal_id.contract_type',
        'sale_proposal_id.contract_type',
        'returned_cheque_ids.sale_proposal_id.contract_type',
    )
    def _compute_contract_type(self):
        for rec in self:
            sale_proposal = (
                    rec.installment_line_id.sale_proposal_id
                    or rec.maintenance_installment_line_id.sale_proposal_id
                    or rec.sale_proposal_id
            )

            if not sale_proposal and rec.returned_cheque_ids:
                proposals = rec.returned_cheque_ids.mapped('sale_proposal_id').filtered(lambda p: p)
                sale_proposal = proposals[0] if len(proposals) == 1 else False

            rec.contract_type = sale_proposal.contract_type if sale_proposal else False

    @api.depends('collection_move_ids')
    def _compute_collection_entry_count(self):
        for rec in self:
            rec.collection_entry_count = len(rec.collection_move_ids) if rec.collection_move_ids else 0

    def action_view_collection_entry(self):
        """Smart button to view collection journal entry"""
        self.ensure_one()
        if not self.collection_move_ids:
            raise UserError(_("No collection journal entry has been created yet."))

        return {
            'name': _('Collection Journal Entry'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.collection_move_ids.ids)],
            'target': 'current',
        }

    def _create_collection_journal_entry(self):
        """Create draft collection journal entry for returned cheque payments and overseas installment payments"""
        self.ensure_one()

        # Skip if collection entry already exists
        if len(self.collection_move_ids) >= 2:
            return None

        # Returned cheque payments: ONLY if selected cheques are Installment
        is_returned_cheque_installment = (
                self.is_returned_cheque
                and self.returned_cheque_ids
                and self.returned_source_type == 'installment'
        )

        # CONDITION 2: Overseas INSTALLMENT payment only (not maintenance)
        is_overseas_installment = (
                self.is_overseas and
                self.overseas_payment_type == 'installment' and
                self.installment_line_id and
                not self.maintenance_installment_line_id
        )

        # Only proceed if one of the conditions is met
        if not (is_returned_cheque_installment or is_overseas_installment):
            return None

        # Get sale proposal from multiple sources
        sale_proposal = None
        if self.installment_line_id and self.installment_line_id.sale_proposal_id:
            sale_proposal = self.installment_line_id.sale_proposal_id
        elif self.sale_proposal_id:
            sale_proposal = self.sale_proposal_id
        elif self.returned_cheque_ids:
            proposals = self.returned_cheque_ids.mapped('sale_proposal_id').filtered(lambda x: x)
            if len(proposals) > 1:
                raise ValidationError(
                    _("Selected cheques belong to different Sale Proposals. Please select cheques from the same contract."))
            sale_proposal = proposals[0] if proposals else None

        # If no sale proposal found, log warning and return
        if not sale_proposal:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning("Cannot create collection entry for payment %s: No sale proposal found" % self.name)
            return None

        Parameters = self.env['ir.config_parameter'].sudo()

        debit_account_id = Parameters.get_param('arkzayed_18_realestate_development.collection_debit_account_id')
        credit_gis_account_id = Parameters.get_param('arkzayed_18_realestate_development.collection_credit_gis_account_id')
        credit_oaya_account_id = Parameters.get_param('arkzayed_18_realestate_development.collection_credit_oaya_account_id')
        gis_percentage = float(Parameters.get_param('arkzayed_18_realestate_development.collection_gis_percentage') or 0)
        oaya_percentage = float(Parameters.get_param('arkzayed_18_realestate_development.collection_oaya_percentage') or 0)
        journal_id = Parameters.get_param('arkzayed_18_realestate_development.collection_journal_id')

        # get analytic accounts
        analytic_accounts = self.env['account.analytic.account']
        # get gis analytic account
        gis_analytic_accounts = analytic_accounts.search([('is_gis_account', '=', True)], limit=1)
        # get oaya analytic account
        oaya_analytic_account = analytic_accounts.search([('is_oaya_account', '=', True)], limit=1)

        if not all([debit_account_id, credit_gis_account_id, credit_oaya_account_id, journal_id]):
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning("Collection entry configuration incomplete in settings")
            return None

        total_amount = self.amount

        # Calculate amounts based on configured percentages
        gis_amount = round((total_amount * gis_percentage) / 100, 2)
        oaya_amount = round((total_amount * oaya_percentage) / 100, 2)

        # Total credit is sum of GIS + OAYA
        total_credit = gis_amount + oaya_amount

        # Debit amount matches the total credit to balance the entry
        debit_amount = total_credit

        moves_to_link = []


        move_vals = {
            'journal_id': int(journal_id),
            'date': self.date or fields.Date.today(),
            'ref': _('Collection - %s - %s') % (sale_proposal.name, self.name),
            'is_gis_quia': True,
        }

        # Credit line 1 - GIS
        if gis_amount > 0:
            gis_move = self.env['account.move'].create(move_vals)
            gis_move.write({
                'line_ids':[
                    (0, 0, {
                        'name': _('Collection Expense - %s') % self.name,
                        'account_id': int(debit_account_id),
                        'partner_id': self.partner_id.id,
                        'debit': gis_amount,
                        'credit': 0.0,
                        'analytic_distribution':{
                            str(gis_analytic_accounts.id): 100.0,
                        }
                    })
                    ,(0, 0, {
                    'name': _('GIS Collection (%.2f%%) - %s') % (gis_percentage, self.name),
                    'account_id': int(credit_gis_account_id),
                    'partner_id': self.partner_id.id,
                    'debit': 0.0,
                    'credit': gis_amount,
                })
                ]})

            moves_to_link.append(gis_move.id)


        # Credit line 2 - OAYA
        if oaya_amount > 0:
            oaya_move = self.env['account.move'].create(move_vals)
            oaya_move.write({
                'line_ids':[
                    (0, 0, {
                        'name': _('Collection Expense - %s') % self.name,
                        'account_id': int(debit_account_id),
                        'partner_id': self.partner_id.id,
                        'debit': oaya_amount,
                        'credit': 0.0,
                        'analytic_distribution':{
                            str(oaya_analytic_account.id): 100.0,
                        }
                    })
                    ,(0, 0, {
                    'name': _('OAYA Collection (%.2f%%) - %s') % (oaya_percentage, self.name),
                    'account_id': int(credit_oaya_account_id),
                    'partner_id': self.partner_id.id,
                    'debit': 0.0,
                    'credit': oaya_amount,
                })]
            })

            moves_to_link.append(oaya_move.id)


        if moves_to_link:
            self.write({
                'collection_move_ids': [Command.link(m_id) for m_id in moves_to_link]
            })

        import logging
        _logger = logging.getLogger(__name__)
        _logger.info("Collection entry created successfully for payment %s: Moves ID %s and %s" % (self.name, moves_to_link[0], moves_to_link[1]))

        return moves_to_link

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



    @api.model
    def create(self, values):
        """Enforce EOI payment to allow only one payment of each type
        (Sent or Received) for every EOI. Each EOI should have only one Sent
        and one Received payment."""

        # Skip validation if context flag is set (for programmatic refund creation)
        skip_validation = self._context.get('skip_eoi_payment_validation', False)

        proposal_id = values.get('sale_proposal_id')
        reservation_id = values.get('sale_reservation_id')
        eoi_id = values.get('eoi_id')
        unit_id = values.get('unit_id')

        # 1. Resolve from Sale Proposal
        if proposal_id:
            proposal = self.env['sale.proposal'].browse(proposal_id)
            if not reservation_id and proposal.sale_contract_reservation_id:
                reservation_id = proposal.sale_contract_reservation_id.id
                values['sale_reservation_id'] = reservation_id
            if not eoi_id:
                eoi = proposal.eoi_id or (
                    proposal.sale_contract_reservation_id.eoi_id
                    if proposal.sale_contract_reservation_id else False
                )
                if eoi:
                    eoi_id = eoi.id
                    values['eoi_id'] = eoi_id
            if not unit_id and proposal.unit_id:
                unit_id = proposal.unit_id.id
                values['unit_id'] = unit_id

        # 2. Resolve from Sale Reservation
        if reservation_id:
            reservation = self.env['real.estate.sale.reservation'].browse(reservation_id)
            if not eoi_id and reservation.eoi_id:
                eoi_id = reservation.eoi_id.id
                values['eoi_id'] = eoi_id
            if not unit_id and reservation.unit_id:
                unit_id = reservation.unit_id.id
                values['unit_id'] = unit_id
            if not proposal_id:
                proposal = self.env['sale.proposal'].search([
                    ('sale_contract_reservation_id', '=', reservation_id),
                    ('state', '!=', 'cancelled')
                ], limit=1)
                if proposal:
                    proposal_id = proposal.id
                    values['sale_proposal_id'] = proposal_id

        # 3. Resolve from EOI
        if eoi_id and not (reservation_id or proposal_id):
            reservation = self.env['real.estate.sale.reservation'].search([
                ('eoi_id', '=', eoi_id),
                ('state', 'not in', ['cancelled', 'expired'])
            ], limit=1)
            proposal = self.env['sale.proposal'].search([
                ('eoi_id', '=', eoi_id),
                ('state', '!=', 'cancelled')
            ], limit=1)
            if proposal:
                values['sale_proposal_id'] = proposal.id
                if proposal.unit_id and not unit_id:
                    values['unit_id'] = proposal.unit_id.id
                if proposal.sale_contract_reservation_id and not reservation_id:
                    values['sale_reservation_id'] = proposal.sale_contract_reservation_id.id
            elif reservation:
                values['sale_reservation_id'] = reservation.id
                if reservation.unit_id and not unit_id:
                    values['unit_id'] = reservation.unit_id.id

        # 4. Resolve from Unit
        if unit_id and not (proposal_id or reservation_id):
            proposal = self.env['sale.proposal'].search([
                ('unit_id', '=', unit_id),
                ('state', '!=', 'cancelled')
            ], limit=1, order='create_date desc')
            reservation = self.env['real.estate.sale.reservation'].search([
                ('unit_id', '=', unit_id),
                ('state', 'not in', ['cancelled', 'expired'])
            ], limit=1, order='create_date desc')

            if proposal:
                values['sale_proposal_id'] = proposal.id
                if proposal.sale_contract_reservation_id and not reservation_id:
                    values['sale_reservation_id'] = proposal.sale_contract_reservation_id.id
                if proposal.eoi_id and not eoi_id:
                    values['eoi_id'] = proposal.eoi_id.id
            elif reservation:
                values['sale_reservation_id'] = reservation.id
                if reservation.eoi_id and not eoi_id:
                    values['eoi_id'] = reservation.eoi_id.id

        # 5. Resolve Partner ID from Proposal, Reservation, or EOI
        if not values.get('partner_id'):
            partner_id = False
            if proposal_id:
                proposal = self.env['sale.proposal'].browse(proposal_id)
                partner_id = proposal.customer_id.id
            elif reservation_id:
                reservation = self.env['real.estate.sale.reservation'].browse(reservation_id)
                partner_id = reservation.customer_id.id
            elif eoi_id:
                eoi = self.env['eoi.eoi'].browse(eoi_id)
                partner_id = eoi.customer_id.id

            if partner_id:
                values['partner_id'] = partner_id

        res = super(AccountPayment, self).create(values)

        for payment in res:
            if payment.from_eoi:
                payment.realestate_related_seq = self.env['ir.sequence'].next_by_code('eoi.account.payment')
            elif payment.from_reservation:
                payment.realestate_related_seq = self.env['ir.sequence'].next_by_code('reservation.account.payment')
            elif payment.from_contract:
                payment.realestate_related_seq = self.env['ir.sequence'].next_by_code('contract.account.payment')
        return res

    def _validate_allocations_on_confirm(self):
        """Validate allocations before confirming payment"""
        for payment in self:
            # Commission claim payments aren't tied to installments, skip allocation validation
            if payment.is_commission_payment:
                continue
            # Force validation if linked to contract/reservation OR if allocation lines exist
            if payment.sale_proposal_id or payment.sale_reservation_id or payment.allocation_ids:
                total_allocated = sum(payment.allocation_ids.mapped('allocated_amount'))
                amount_company_currency = payment._get_amount_company_currency()
                if round(total_allocated, 2) != round(amount_company_currency, 2):
                    raise ValidationError(_(
                        "Cannot confirm payment: The total allocated amount (%(alloc).2f) must be equal to the payment amount (%(amt).2f).\n"
                        "Unallocated Balance: %(unalloc).2f",
                        alloc=total_allocated,
                        amt=amount_company_currency,
                        unalloc=payment.unallocated_amount
                    ))

                for alloc in payment.allocation_ids:
                    line = alloc.installment_id or alloc.maintenance_id
                    if line and round(alloc.allocated_amount, 2) > round(line.remaining_amount, 2):
                        # Name the contract/reservation the line itself belongs to, which
                        # may be an additional contract rather than the payment's main one.
                        line_ref = line.sale_proposal_id or line.reservation_id
                        ref_name = line_ref.name if line_ref else ""
                        raise ValidationError(_(
                            "Cannot confirm payment: For line '%(line)s' in %(ref)s, "
                            "the allocated amount (%(alloc).2f) is greater than the line remaining amount (%(rem).2f).",
                            line=line.name,
                            ref=ref_name,
                            alloc=alloc.allocated_amount,
                            rem=line.remaining_amount
                        ))

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
            # Handle is_down_payment
            if self.is_down_payment:
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

        # Handle is_down_payment
        if self.partner_id:
            if self.is_down_payment:
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

            if self.is_returned_cheque and self.partner_id:
                notes_receivable_account = self.partner_id.property_notes_receivable_account_id
                if not notes_receivable_account:
                    raise ValidationError(
                        _("Notes Receivable Account is not configured for partner %s")
                        % self.partner_id.name)
                else:
                    for line_vals in line_vals_list:
                        if line_vals.get('account_id') == self.partner_id.property_account_receivable_id.id:
                            line_vals['account_id'] = notes_receivable_account.id

        return line_vals_list

    def action_post(self):
        """Override to trigger broker claim, move flags, and commission check when payment is posted"""
        self._validate_allocations_on_confirm()
        self._check_down_payment_accounts()

        result = super(AccountPayment, self).action_post()

        for payment in self:
            allocated_insts = payment.allocation_ids.mapped('installment_id')
            allocated_maints = payment.allocation_ids.mapped('maintenance_id')

            is_installment_payment = bool(payment.installment_line_id) or bool(allocated_insts)
            is_maintenance_payment = bool(payment.maintenance_installment_line_id) or bool(allocated_maints)

            if payment.move_id:
                move_flags = {}

                if is_installment_payment:
                    move_flags['is_collection'] = True

                if is_maintenance_payment:
                    move_flags['is_maintenance_collection'] = True

                if move_flags:
                    payment.move_id.write(move_flags)

            if payment.is_returned_cheque and payment.returned_cheque_ids:
                payment.returned_cheque_ids.write({
                    'is_returned_paid': True,
                    'returned_payment_id': payment.id,
                })

            # Every contract settled by this payment (main + additional) must be
            # recomputed, not just one. Gather them from the allocations plus any
            # legacy direct links / main proposal.
            proposals_to_update = (
                allocated_insts.mapped('sale_proposal_id')
                | allocated_maints.mapped('sale_proposal_id')
            ).filtered(lambda p: p)

            legacy_proposal = (
                payment.installment_line_id.sale_proposal_id
                or payment.maintenance_installment_line_id.sale_proposal_id
                or payment.sale_proposal_id
            )
            if legacy_proposal:
                proposals_to_update |= legacy_proposal

            for sale_proposal in proposals_to_update:
                # Whether this specific contract is settled through installment lines
                # (as opposed to maintenance only) decides commission/broker triggers.
                has_installment = bool(
                    payment.installment_line_id
                    and payment.installment_line_id.sale_proposal_id == sale_proposal
                ) or bool(allocated_insts.filtered(lambda l: l.sale_proposal_id == sale_proposal))

                # Trigger the robust calculation directly on the proposal
                sale_proposal._compute_collection_amounts()

                if sale_proposal._is_commission_eligible() and has_installment:
                    sale_proposal._auto_create_commission_achievements()

                if sale_proposal.referred_by == 'broker' and has_installment:
                    sale_proposal._check_and_create_broker_claim()

                if has_installment:
                    sale_proposal._check_and_create_non_sales_claims()

            if payment.state == 'paid':
                self.update_broker_claim(payment.id)
        return result

    def _check_down_payment_accounts(self):
        for rec in self:
            if rec.is_down_payment and not rec.partner_id.property_account_down_payment_receivable_id:
                raise ValidationError(_("Please set 'Account Down Payment Receivable' for partner %s") % rec.partner_id.name)
            if rec.is_pre_payment and not rec.partner_id.property_account_down_payment_payable_id:
                raise ValidationError(_("Please set 'Account Down Payment Payable' for partner %s") % rec.partner_id.name)

    def update_broker_claim(self, payment):
        broker_claim = self.env['broker.claim'].search([
            ('payment_id', '=', payment)
        ], limit=1)
        if broker_claim and broker_claim.state != 'paid':
            broker_claim.write({
                'state': 'paid',
                'payment_date': fields.Date.today()
            })

    def action_draft(self):
        super(AccountPayment, self).action_draft()
        for payment in self:
            broker_claim = self.env['broker.claim'].search([
                ('payment_id', '=', payment.id)
            ], limit=1)
            if broker_claim and broker_claim.state != 'draft':
                broker_claim.write({
                    'state': 'confirmed',
                    'payment_date': False
                })

    def button_draft(self):
        """Override to recompute collection when payment is reset to draft"""
        result = super(AccountPayment, self).button_draft()

        # Recompute collection amounts when payment is cancelled
        for payment in self:
            sale_proposal = None

            # Check regular installments
            if payment.installment_line_id and payment.installment_line_id.sale_proposal_id:
                sale_proposal = payment.installment_line_id.sale_proposal_id

            # Check maintenance installments
            elif payment.maintenance_installment_line_id and payment.maintenance_installment_line_id.sale_proposal_id:
                sale_proposal = payment.maintenance_installment_line_id.sale_proposal_id

            # Recompute if applicable
            if sale_proposal and sale_proposal._is_commission_eligible():
                sale_proposal._compute_collection_amounts()

        return result

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

    @api.depends(
        'sale_proposal_id.unit_id',
        'sale_reservation_id.unit_id',
        'allocation_ids.installment_id.unit_id',
        'allocation_ids.maintenance_id.unit_id'
    )
    def _compute_unit_id(self):
        for rec in self:
            if rec.sale_proposal_id and rec.sale_proposal_id.unit_id:
                rec.unit_id = rec.sale_proposal_id.unit_id
            elif rec.sale_reservation_id and rec.sale_reservation_id.unit_id:
                rec.unit_id = rec.sale_reservation_id.unit_id
            elif rec.allocation_ids:
                alloc_units = (
                        rec.allocation_ids.mapped('installment_id.unit_id') |
                        rec.allocation_ids.mapped('maintenance_id.unit_id')
                ).filtered(lambda u: u)
                rec.unit_id = alloc_units[0] if alloc_units else rec.unit_id
            else:
                rec.unit_id = rec.unit_id

    @api.onchange('eoi_id')
    def _onchange_eoi_id(self):
        """Selecting EOI populates linked Reservation, Proposal, and Unit if they exist"""
        if self.eoi_id:
            if self.eoi_id.customer_id:
                self.partner_id = self.eoi_id.customer_id

            reservation = self.env['real.estate.sale.reservation'].search([
                ('eoi_id', '=', self.eoi_id.id),
                ('state', 'not in', ['cancelled', 'expired'])
            ], limit=1)
            proposal = self.env['sale.proposal'].search([
                ('eoi_id', '=', self.eoi_id.id),
                ('state', '!=', 'cancelled')
            ], limit=1)

            if proposal:
                self.sale_proposal_id = proposal
                self.sale_reservation_id = proposal.sale_contract_reservation_id or reservation
                if proposal.unit_id:
                    self.unit_id = proposal.unit_id
            elif reservation:
                self.sale_reservation_id = reservation
                if reservation.unit_id:
                    self.unit_id = reservation.unit_id

    @api.onchange('unit_id')
    def _onchange_unit_id(self):
        """Selecting Unit populates Contract, Reservation, and EOI if they exist"""
        if self.unit_id:
            proposal = self.env['sale.proposal'].search([
                ('unit_id', '=', self.unit_id.id),
                ('state', '!=', 'cancelled')
            ], limit=1, order='create_date desc')

            reservation = self.env['real.estate.sale.reservation'].search([
                ('unit_id', '=', self.unit_id.id),
                ('state', 'not in', ['cancelled', 'expired'])
            ], limit=1, order='create_date desc')

            if proposal:
                self.sale_proposal_id = proposal
                self.sale_reservation_id = proposal.sale_contract_reservation_id or reservation
                self.eoi_id = proposal.eoi_id or (
                    self.sale_reservation_id.eoi_id if self.sale_reservation_id else False)
                if proposal.customer_id:
                    self.partner_id = proposal.customer_id
            elif reservation:
                self.sale_reservation_id = reservation
                if reservation.eoi_id:
                    self.eoi_id = reservation.eoi_id
                if reservation.customer_id:
                    self.partner_id = reservation.customer_id

    @api.onchange('sale_reservation_id')
    def _onchange_sale_reservation_id(self):
        """Selecting Reservation populates Unit, EOI, and Contract if they exist"""
        if self.sale_reservation_id:
            res = self.sale_reservation_id
            if res.customer_id:
                self.partner_id = res.customer_id
            if res.unit_id:
                self.unit_id = res.unit_id
            if res.eoi_id:
                self.eoi_id = res.eoi_id

            proposal = self.env['sale.proposal'].search([
                ('sale_contract_reservation_id', '=', res.id),
                ('state', '!=', 'cancelled')
            ], limit=1)
            if proposal:
                self.sale_proposal_id = proposal

    @api.onchange('sale_proposal_id')
    def _onchange_sale_proposal_id(self):
        """Selecting Proposal populates Unit, Reservation, and EOI if they exist"""
        if self.sale_proposal_id:
            prop = self.sale_proposal_id
            if prop.customer_id:
                self.partner_id = prop.customer_id
            if prop.unit_id:
                self.unit_id = prop.unit_id
            if prop.sale_contract_reservation_id:
                self.sale_reservation_id = prop.sale_contract_reservation_id
            self.eoi_id = prop.eoi_id or (
                prop.sale_contract_reservation_id.eoi_id
                if prop.sale_contract_reservation_id else False
            )