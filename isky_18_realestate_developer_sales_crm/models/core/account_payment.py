# -*- coding: utf-8 -*-
from odoo import models, fields, api, _, Command
from odoo.exceptions import ValidationError

from odoo.addons.isky_18_realestate_developer_unit_inventory.models.selections import contract_type_selection


class AccountPayment(models.Model):
    _inherit = "account.payment"

    # Phase 3 step 2a: sales-owned flag, moved here from the L1 accounting bridge. The bridge
    # keeps the down-payment ACCOUNT SELECTION (that is accounting behaviour) and reads this
    # flag via getattr, so it stays installable without sales_crm.
    is_down_payment = fields.Boolean()

    sale_reservation_id = fields.Many2one("real.estate.sale.reservation", "Sale Reservation")
    sale_proposal_id = fields.Many2one("sale.proposal", "Sale Proposal")
    loan_line_id = fields.Many2one("loan.line", "Loan Line")
    eoi_id = fields.Many2one('eoi.eoi', 'EOI', domain=[('status', '=', 'new')])
    installment_line_id = fields.Many2one('installment.lines')
    maintenance_installment_line_id = fields.Many2one('maintenance.installment.lines', string='Maintenance Installment')

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

    # S6 guard pattern: this base compute depends only on always-present paths, so sales_crm
    # loads with no accounting layer (Mode B). isky_18_realestate_developer_sales_accounting
    # redeclares it with 'custom_exchange_rate' / 'converted_amount' added and calls super().
    @api.depends('amount', 'currency_id', 'date', 'company_id', 'allocation_ids.allocated_amount')
    def _compute_unallocated(self):
        for rec in self:
            total_allocated = sum(rec.allocation_ids.mapped('allocated_amount'))
            rec.unallocated_amount = max(0.0, rec._get_amount_company_currency() - total_allocated)

    def _get_amount_company_currency(self):
        """allocated_amount on payment.allocation is always expressed in the company
        currency (it mirrors installment.lines.remaining_amount, itself tied to
        company_id.currency_id). A payment can be registered in another currency
        (e.g. USD), so convert its amount before comparing it to allocations.

        Base (Mode B): convert at the currency rate on the payment date. sales_accounting
        extends this to honour a user-edited custom_exchange_rate instead, when one is set."""
        self.ensure_one()
        company_currency = self.company_id.currency_id
        if self.currency_id == company_currency:
            return self.amount
        return self.currency_id._convert(
            self.amount, company_currency, self.company_id, self.date or fields.Date.context_today(self)
        )

    @api.depends(
        'installment_line_id.sale_proposal_id.contract_type',
        'maintenance_installment_line_id.sale_proposal_id.contract_type',
        'sale_proposal_id.contract_type',
    )
    def _compute_contract_type(self):
        for rec in self:
            sale_proposal = (
                    rec.installment_line_id.sale_proposal_id
                    or rec.maintenance_installment_line_id.sale_proposal_id
                    or rec.sale_proposal_id
            )

            if not sale_proposal:
                sale_proposal = rec._returned_cheque_proposal()

            rec.contract_type = sale_proposal.contract_type if sale_proposal else False

    # ----------------------------------------------------------------------------------
    # Cheque hooks (supplement S1, Phase 3 step 4). sales_cheques overrides each one.
    # ----------------------------------------------------------------------------------

    def _returned_cheque_proposal(self):
        """The single contract behind this payment's returned cheques, if exactly one."""
        return False

    def _mark_returned_cheques_paid(self):
        """Stamp the returned cheques this payment settles."""
        return

    @api.depends('collection_move_ids')
    def _compute_collection_entry_count(self):
        for rec in self:
            rec.collection_entry_count = len(rec.collection_move_ids) if rec.collection_move_ids else 0

    def action_view_collection_entry(self):
        """Smart button to view collection journal entry"""
        self.ensure_one()
        if not self.collection_move_ids:
            raise ValidationError(_("No collection journal entry has been created yet."))

        return {
            'name': _('Collection Journal Entry'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.collection_move_ids.ids)],
            'target': 'current',
        }

    # _create_collection_journal_entry moved to
    # isky_18_realestate_developer_sales_accounting (Phase 3 step 2b-a): it creates
    # account.move records and reads bridge-owned fields (is_overseas,
    # overseas_payment_type, is_revenue_split_entry), so it is Mode A only. In Mode B it
    # does not exist and no journal entry is produced, per supplement S2.
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

    def action_post(self):
        """Override to trigger broker claim, move flags, and commission check when payment is posted.
        update_broker_claim (checking payment.state == 'paid') is handled by a further override
        in isky_18_realestate_developer_commission, chained via super()."""
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

            payment._mark_returned_cheques_paid()

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
        return result

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

    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None, **kwargs):
        """Layer the returned-cheque notes-receivable account swap on top of the
        accounting bridge's own override (overseas/down-payment account selection)."""
        line_vals_list = super(AccountPayment, self)._prepare_move_line_default_vals(
            write_off_line_vals=write_off_line_vals, force_balance=force_balance, **kwargs
        )

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

    is_returned_cheque = fields.Boolean(
        string='Is Returned Cheque',
        default=False,
        help='Flag to indicate if this payment is for a returned cheque that requires collection entry'
    )
    # cheque_id, returned_cheque_ids and returned_source_type - plus the onchange and the
    # constrains over them - moved to isky_18_realestate_developer_sales_cheques (Phase 3
    # step 4). is_returned_cheque stays here: it is a plain flag with no cheque coupling,
    # and _prepare_move_line_default_vals() below branches on it.
