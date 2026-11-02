from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class PaymentAllocation(models.Model):
    _name = 'payment.allocation'
    _description = 'Payment & Cheque Allocation'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    payment_id = fields.Many2one('account.payment', string='Payment', ondelete='cascade', tracking=True)
    cheque_id = fields.Many2one('cheque.manage', string='Cheque', ondelete='cascade', tracking=True)

    installment_id = fields.Many2one('installment.lines', string='Unit Installment', ondelete='cascade', tracking=True)
    maintenance_id = fields.Many2one('maintenance.installment.lines', string='Maintenance Installment',
                                     ondelete='cascade', tracking=True)

    allocated_amount = fields.Float(string='Allocated Amount', required=True, tracking=True)

    # Helper fields computed specifically for payment allocation display
    source_doc = fields.Char(string='Source Document', compute='_compute_line_details', tracking=True)
    line_date = fields.Date(string='Installment Date', compute='_compute_line_details', tracking=True)
    line_remaining_amount = fields.Float(string='Remaining Balance', compute='_compute_line_details', digits=(16, 4), tracking=True)
    label = fields.Char(string="Label")

    @api.model
    def execute_data_migration(self):
        """
        Comprehensive Historical Payment Allocation Migration:
        Phase 1: Migrate explicit Many2one direct links (installment_line_id / maintenance_installment_line_id).
        Phase 1.5: Migrate Down Payment payments/cheques (is_down_payment / from_down_payment) directly to Down Payment lines.
        Phase 2: Waterfall leftover unallocated balances partitioned strictly by source_type ('installment' vs 'maintenance').
        """
        import logging
        _logger = logging.getLogger(__name__)

        _logger.info("Starting Complete Historical Payment Allocation Migration...")

        alloc_model = self.with_context(skip_allocation_check=True)
        alloc_model.search([]).unlink()

        def _is_maint_rec(rec):
            if getattr(rec, 'source_type', False) == 'maintenance':
                return True
            if getattr(rec, 'overseas_payment_type', False) == 'maintenance':
                return True
            if bool(getattr(rec, 'maintenance_installment_line_id', False)):
                return True
            return False

        def _is_dp_rec(rec):
            return bool(
                getattr(rec, 'from_eoi', False) or
                getattr(rec, 'is_down_payment', False) or
                getattr(rec, 'from_down_payment', False)
            )

        def _process_doc(doc, is_proposal=True):
            payments = doc.payment_ids.filtered(
                lambda p: p.payment_type == 'inbound') if is_proposal else doc.account_payment_ids.filtered(
                lambda p: p.payment_type == 'inbound')
            cheques = doc.cheque_ids if is_proposal else doc.cheque_manage_ids

            if not payments and not cheques:
                return

            # =========================================================================
            # STEP A: EXPLICIT MANY2ONE DIRECT LINKS
            # =========================================================================
            for p in payments:
                if p.installment_line_id:
                    if not alloc_model.search(
                            [('payment_id', '=', p.id), ('installment_id', '=', p.installment_line_id.id)]):
                        alloc_model.create({'payment_id': p.id, 'installment_id': p.installment_line_id.id,
                                            'allocated_amount': p.amount})
                elif p.maintenance_installment_line_id:
                    if not alloc_model.search(
                            [('payment_id', '=', p.id), ('maintenance_id', '=', p.maintenance_installment_line_id.id)]):
                        alloc_model.create({'payment_id': p.id, 'maintenance_id': p.maintenance_installment_line_id.id,
                                            'allocated_amount': p.amount})

            for c in cheques:
                if c.installment_line_id:
                    if not alloc_model.search(
                            [('cheque_id', '=', c.id), ('installment_id', '=', c.installment_line_id.id)]):
                        alloc_model.create({'cheque_id': c.id, 'installment_id': c.installment_line_id.id,
                                            'allocated_amount': c.amount})
                elif c.maintenance_installment_line_id:
                    if not alloc_model.search(
                            [('cheque_id', '=', c.id), ('maintenance_id', '=', c.maintenance_installment_line_id.id)]):
                        alloc_model.create({'cheque_id': c.id, 'maintenance_id': c.maintenance_installment_line_id.id,
                                            'allocated_amount': c.amount})

            # =========================================================================
            # STEP B: DOWN PAYMENT PRIORITY MATCHING (FOR RESERVATIONS & CONTRACTS)
            # =========================================================================
            dp_lines = doc.installment_ids.filtered(
                lambda l: getattr(l, 'is_down_payment', False) or
                          getattr(l, 'is_down_payment_reservation', False) or
                          (l.name and 'Down Payment' in l.name)
            ).sorted(key=lambda l: (l.date is False, l.date, l.serial))

            if dp_lines:
                dp_line = dp_lines[0]
                dp_line_total = (dp_line.total_amount if dp_line.total_amount else dp_line.amount)

                # Down Payment Payments with no explicit line link (EOI prioritized first)
                dp_payments = payments.filtered(lambda rec: _is_dp_rec(rec) and not rec.installment_line_id).sorted(
                    key=lambda p: (not getattr(p, 'from_eoi', False), p.date is False, p.date)
                )
                for p in dp_payments:
                    already_alloc = sum(alloc_model.search([('payment_id', '=', p.id)]).mapped('allocated_amount'))
                    unalloc = p.amount - already_alloc
                    if unalloc > 0.0001:
                        line_already_alloc = sum(
                            alloc_model.search([('installment_id', '=', dp_line.id)]).mapped('allocated_amount'))
                        needed = max(0.0, dp_line_total - line_already_alloc)
                        alloc_amt = min(unalloc, needed) if needed > 0.0001 else unalloc
                        alloc_model.create({
                            'payment_id': p.id,
                            'installment_id': dp_line.id,
                            'allocated_amount': alloc_amt,
                        })
                        dp_line.write({'payment_method_used': 'payment'})

                # Down Payment Cheques with no explicit line link (EOI prioritized first)
                dp_cheques = cheques.filtered(lambda rec: _is_dp_rec(rec) and not rec.installment_line_id).sorted(
                    key=lambda c: (
                        not getattr(c, 'from_eoi', False),
                        (c.cheque_date or c.cheque_receive_date) is False,
                        c.cheque_date or c.cheque_receive_date
                    )
                )
                for c in dp_cheques:
                    already_alloc = sum(alloc_model.search([('cheque_id', '=', c.id)]).mapped('allocated_amount'))
                    unalloc = c.amount - already_alloc
                    if unalloc > 0.0001:
                        line_already_alloc = sum(
                            alloc_model.search([('installment_id', '=', dp_line.id)]).mapped('allocated_amount'))
                        needed = max(0.0, dp_line_total - line_already_alloc)
                        alloc_amt = min(unalloc, needed) if needed > 0.0001 else unalloc
                        alloc_model.create({
                            'cheque_id': c.id,
                            'installment_id': dp_line.id,
                            'allocated_amount': alloc_amt,
                        })
                        dp_line.write({'payment_method_used': 'cheque'})

            # =========================================================================
            # STEP C: WATERFALL LEFTOVER FUNDS PARTITIONED STRICTLY BY SOURCE TYPE
            # =========================================================================
            inst_funds = []
            maint_funds = []

            for p in payments:
                alloc = sum(alloc_model.search([('payment_id', '=', p.id)]).mapped('allocated_amount'))
                unalloc = p.amount - alloc
                if unalloc > 0.0001:
                    item = {'type': 'payment', 'rec': p, 'rem': unalloc, 'date': p.date or fields.Date.today()}
                    (maint_funds if _is_maint_rec(p) else inst_funds).append(item)

            for c in cheques:
                alloc = sum(alloc_model.search([('cheque_id', '=', c.id)]).mapped('allocated_amount'))
                unalloc = c.amount - alloc
                if unalloc > 0.0001:
                    item = {'type': 'cheque', 'rec': c, 'rem': unalloc,
                            'date': c.cheque_date or c.cheque_receive_date or fields.Date.today()}
                    (maint_funds if _is_maint_rec(c) else inst_funds).append(item)

            def _distribute(funds, lines, ltype):
                if not funds or not lines:
                    return
                # Sort funds: EOI payments/cheques first, then chronologically by date
                funds.sort(key=lambda x: (
                    not getattr(x['rec'], 'from_eoi', False),
                    x['date'] is False,
                    x['date']
                ))

                def _get_needed(line):
                    if ltype == 'installment':
                        alloc_so_far = sum(
                            alloc_model.search([('installment_id', '=', line.id)]).mapped('allocated_amount'))
                    else:
                        alloc_so_far = sum(
                            alloc_model.search([('maintenance_id', '=', line.id)]).mapped('allocated_amount'))
                    ltotal = line.total_amount if line.total_amount else line.amount
                    return max(0.0, ltotal - alloc_so_far)

                unpaid_lines = [l for l in lines if _get_needed(l) > 0.0001]
                unpaid_lines.sort(key=lambda l: (l.date is False, l.date, l.serial))

                for line in unpaid_lines:
                    needed = _get_needed(line)
                    for fund in funds:
                        if fund['rem'] <= 0.0001:
                            continue
                        if needed <= 0.0001:
                            break

                        alloc_amt = min(fund['rem'], needed)
                        alloc_vals = {'allocated_amount': alloc_amt}
                        if fund['type'] == 'payment':
                            alloc_vals['payment_id'] = fund['rec'].id
                        else:
                            alloc_vals['cheque_id'] = fund['rec'].id

                        if ltype == 'installment':
                            alloc_vals['installment_id'] = line.id
                        else:
                            alloc_vals['maintenance_id'] = line.id

                        alloc_model.create(alloc_vals)
                        fund['rem'] -= alloc_amt
                        needed -= alloc_amt
                        line.write({'payment_method_used': 'payment' if fund['type'] == 'payment' else 'cheque'})

            # Distribute Unit Installment funds ONLY to Unit Installment lines
            _distribute(inst_funds, doc.installment_ids, 'installment')

            # Distribute Maintenance funds ONLY to Maintenance Installment lines
            maint_lines = getattr(doc, 'maintenance_installment_ids', self.env['maintenance.installment.lines'])
            _distribute(maint_funds, maint_lines, 'maintenance')

        # Run on proposals and reservations
        for proposal in self.env['sale.proposal'].search([]):
            _process_doc(proposal, is_proposal=True)

        for reservation in self.env['real.estate.sale.reservation'].search([]):
            _process_doc(reservation, is_proposal=False)

        # =========================================================================
        # PERMANENTLY DELETE THE UI BUTTON / SERVER ACTION
        # =========================================================================
        action = self.env.ref('arkzayed_18_realestate_development.action_server_execute_data_migration_reservation',
                              raise_if_not_found=True)
        action2 = self.env.ref('arkzayed_18_realestate_development.action_server_execute_data_migration_contract',
                               raise_if_not_found=True)

        if action:
            action.unlink()
            _logger.info("Migration complete: Reservation Server Action permanently deleted from UI.")

        if action2:
            action2.unlink()
            _logger.info("Migration complete: Contract Server Action permanently deleted from UI.")

        return True

    @api.depends('installment_id', 'maintenance_id')
    def _compute_line_details(self):
        """Compute source document, date, and remaining balance for allocation table display"""
        for rec in self:
            line = rec.installment_id or rec.maintenance_id
            if line:
                ref_parts = []
                if getattr(line, 'reservation_id', False) and line.reservation_id.name:
                    ref_parts.append(line.reservation_id.name)
                if getattr(line, 'sale_proposal_id', False) and line.sale_proposal_id.name not in ref_parts:
                    ref_parts.append(line.sale_proposal_id.name)

                rec.source_doc = " / ".join(ref_parts) if ref_parts else "-"
                rec.line_date = line.date
                rec.line_remaining_amount = line.remaining_amount
            else:
                rec.source_doc = False
                rec.line_date = False
                rec.line_remaining_amount = 0.0

    @api.onchange('installment_id', 'maintenance_id')
    def _onchange_installment_maintenance(self):
        parent = self.payment_id or self.cheque_id
        if not parent:
            return

        # Include the main contract plus any additional contracts on the payment
        # (cheques do not carry additional contracts).
        proposals = parent.sale_proposal_id
        additional = getattr(parent, 'additional_proposal_ids', False)
        if additional:
            proposals |= additional
        reservation = parent.sale_reservation_id

        def _ref_names():
            names = list(proposals.mapped('name'))
            if reservation:
                names.append(reservation.name)
            return ', '.join(filter(None, names))

        if proposals or reservation:
            # Union of recordsets naturally handles and deduplicates lines
            inst_lines = proposals.mapped('installment_ids') | \
                         (reservation.installment_ids if reservation else self.env['installment.lines'])

            maint_lines = proposals.mapped('maintenance_installment_ids') | \
                          (reservation.maintenance_installment_ids if reservation else self.env[
                              'maintenance.installment.lines'])

            if not inst_lines and not maint_lines:
                raise UserError(
                    _("Please calculate installments for %s first before allocating payments.") % _ref_names()
                )

            unpaid_insts = inst_lines.filtered(lambda l: l.remaining_amount > 0)
            unpaid_maints = maint_lines.filtered(lambda l: l.remaining_amount > 0)

            if not unpaid_insts and not unpaid_maints:
                raise UserError(_("The corresponding contract/reservation (%s) is already fully paid.") % _ref_names())

        # Automatically default allocated_amount to selected line's remaining amount
        line = self.installment_id or self.maintenance_id
        if line:
            self.allocated_amount = line.remaining_amount

    @api.constrains('allocated_amount', 'installment_id', 'maintenance_id')
    def _check_allocated_amount_limit(self):
        # Skip validation during migration or automated reallocation loops
        if self.env.context.get('skip_allocation_check'):
            return

        for rec in self:
            line = rec.installment_id or rec.maintenance_id
            if line and round(rec.allocated_amount, 2) > round(line.remaining_amount, 2):
                raise ValidationError(_(
                    "The allocated amount (%(alloc).2f) for line '%(line)s' cannot be greater than its remaining amount (%(rem).2f).",
                    alloc=rec.allocated_amount,
                    line=line.name,
                    rem=line.remaining_amount
                ))

    @api.constrains('payment_id', 'cheque_id', 'installment_id', 'maintenance_id')
    def _check_unique_allocation_line(self):
        # Skip validation during migration or automated reallocation loops
        if self.env.context.get('skip_allocation_check'):
            return

        for rec in self:
            if rec.payment_id:
                if rec.installment_id and self.search_count([
                    ('id', '!=', rec.id),
                    ('payment_id', '=', rec.payment_id.id),
                    ('installment_id', '=', rec.installment_id.id),
                ]) > 0:
                    raise ValidationError(_(
                        "The unit installment '%(line)s' is already selected in this payment.",
                        line=rec.installment_id.name
                    ))

                if rec.maintenance_id and self.search_count([
                    ('id', '!=', rec.id),
                    ('payment_id', '=', rec.payment_id.id),
                    ('maintenance_id', '=', rec.maintenance_id.id),
                ]) > 0:
                    raise ValidationError(_(
                        "The maintenance installment '%(line)s' is already selected in this payment.",
                        line=rec.maintenance_id.name
                    ))

            if rec.cheque_id:
                if rec.installment_id and self.search_count([
                    ('id', '!=', rec.id),
                    ('cheque_id', '=', rec.cheque_id.id),
                    ('installment_id', '=', rec.installment_id.id),
                ]) > 0:
                    raise ValidationError(_(
                        "The unit installment '%(line)s' is already selected in this cheque.",
                        line=rec.installment_id.name
                    ))

                if rec.maintenance_id and self.search_count([
                    ('id', '!=', rec.id),
                    ('cheque_id', '=', rec.cheque_id.id),
                    ('maintenance_id', '=', rec.maintenance_id.id),
                ]) > 0:
                    raise ValidationError(_(
                        "The maintenance installment '%(line)s' is already selected in this cheque.",
                        line=rec.maintenance_id.name
                    ))