from odoo.addons.isky_18_realestate_developer_unit_inventory.models.selections import contract_type_selection
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.translate import _

# Ticking an installment as Paid by hand counts money that has no payment or cheque behind it.
# Defined in this module's own security/security.xml (Phase 3 step 1): it gates an
# installment.lines action, and while it lived in the monolith sales_crm did not depend on
# that module, so has_group() always returned False and the button was dead.
MANUAL_PAID_GROUP = 'isky_18_realestate_developer_sales_crm.group_manual_paid_installment'


class LoanLine(models.Model):
    _name = "installment.lines"
    _description = "Installments"
    _order = "serial"

    name = fields.Char("Name")
    date = fields.Date("Date")
    serial = fields.Integer("#")
    amount = fields.Float("Payment", digits=(16, 4))
    amount_due = fields.Float(digits=(16, 4))
    total_amount = fields.Float("Total Amount", compute='calculate_total_amount', digits=(16, 4))
    is_down_payment = fields.Boolean("Is Down Payment", default=False)
    paid_amount = fields.Float(
        "Paid Amount",
        compute='_compute_paid_remaining',
        store=True,
        digits=(16, 4),
        help="Amount actually collected for this installment."
    )
    remaining_amount = fields.Float(
        "Remaining Amount",
        compute='_compute_paid_remaining',
        store=True,
        digits=(16, 4),
        help="Outstanding amount still to be collected."
    )
    payment_ids = fields.One2many('account.payment', 'installment_line_id', string="Payments")
    # cheque_ids moved to isky_18_realestate_developer_sales_cheques (Phase 3 step 3).

    paid = fields.Boolean(
        "Paid",
        compute='_compute_paid',
        store=True,
        readonly=False,
        help="Automatically set to True when payment is posted or cheque is done. "
             "It can also be set by hand, but only by the users of the group "
             "'Can Tick Installments as Paid': a ticked installment then counts as fully "
             "collected, even for the part no payment or cheque covers."
    )
    # Supplement S2: "Setting Paid stores date and user". Recorded as fields, not only in the
    # chatter, so Mode B has a queryable record of who acknowledged the money and when.
    paid_date = fields.Datetime(string='Paid On', readonly=True, copy=False)
    paid_by_id = fields.Many2one('res.users', string='Paid By', readonly=True, copy=False)

    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)

    reservation_id = fields.Many2one("real.estate.sale.reservation", "", ondelete="cascade", readonly=True)
    sale_proposal_id = fields.Many2one("sale.proposal", "", ondelete="cascade", readonly=True)
    is_sale_proposal_vip = fields.Boolean(related="sale_proposal_id.is_vip")
    vip_badge = fields.Char(string='VIP', compute='_compute_vip_badge', store=True)
    customer_id = fields.Many2one(related="sale_proposal_id.customer_id", )
    state = fields.Selection(related="sale_proposal_id.state", )

    contract_state = fields.Selection(
        related='sale_proposal_id.state',
        string='Contract State',
        store=True,
        readonly=True
    )

    partner_id = fields.Many2one('res.partner', string="Partner")
    journal_id = fields.Many2one('account.journal')

    # Currency and Residual fallbacks to prevent view crashes
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
    amount_residual = fields.Monetary(compute='_compute_amount_residual', readonly=True)

    # Computed fields for view state badges
    payment_state = fields.Char(string="Payment State", compute="_compute_states")
    # cheque_state moved to isky_18_realestate_developer_sales_cheques; the bridge also
    # extends _compute_states to fill it.

    tax_ids = fields.Many2many("account.tax", string="Tax")
    vat_id = fields.Many2one("account.tax", string="Vat")

    payment_methods = fields.Selection(related="sale_proposal_id.payment_methods", store=True)
    payment_method_used = fields.Selection([
        ('payment', 'Payment'),
        ('cheque', 'Cheque'),
        ('both', 'Payment & Cheque'),
    ], string='Payment Method Used', compute='_compute_payment_method_used', store=True)

    unit_id = fields.Many2one('real.estate.unit', string="Unit", compute='_compute_unit_id', store=True)
    contract_type = fields.Selection(selection=contract_type_selection, compute='_compute_contract_type', store=True)
    is_overdue = fields.Boolean(compute='_compute_is_overdue', store=True)
    overdue_days = fields.Integer(string="Overdue Days", compute='_compute_is_overdue', store=True)
    is_down_payment_reservation = fields.Boolean()

    allocation_ids = fields.One2many('payment.allocation', 'installment_id', string='Allocations')

    allocated_payment_ids = fields.Many2many(
        'account.payment',
        string='Allocated Payments',
        compute='_compute_allocated_records'
    )
    # allocated_cheque_ids moved to isky_18_realestate_developer_sales_cheques.

    # S6: base depends on payment paths only; sales_cheques redeclares with the cheque paths
    # added, calls super(), and fills allocated_cheque_ids.
    @api.depends('allocation_ids.payment_id')
    def _compute_allocated_records(self):
        for rec in self:
            rec.allocated_payment_ids = rec.allocation_ids.mapped('payment_id')

    @api.depends('allocation_ids.payment_id.move_id.amount_residual')
    def _compute_amount_residual(self):
        """Calculates the true unreconciled residual amount from the linked accounting moves"""
        for rec in self:
            payments = rec.allocation_ids.mapped('payment_id')
            if payments:
                rec.amount_residual = sum(p.move_id.amount_residual for p in payments if p.move_id)
            else:
                rec.amount_residual = 0.0

    @api.depends('allocation_ids.payment_id')
    def _compute_payment_method_used(self):
        for rec in self:
            has_payment = any(alloc.payment_id for alloc in rec.allocation_ids)
            has_cheque = rec._has_cheque_allocation()

            if has_payment and has_cheque:
                rec.payment_method_used = 'both'
            elif has_payment:
                rec.payment_method_used = 'payment'
            elif has_cheque:
                rec.payment_method_used = 'cheque'
            else:
                rec.payment_method_used = False

    # S6: base computes payment_state only; sales_cheques redeclares with the cheque paths
    # added, calls super(), and fills cheque_state.
    @api.depends('allocation_ids.payment_id.state')
    def _compute_states(self):
        """Summarizes the state of linked payments for the UI badge"""
        EXCLUDED_PAYMENT_STATES = ('canceled', 'rejected')
        PAID_PAYMENT_STATES = ('paid',)

        for rec in self:
            # 1. Payment State Logic
            valid_payments = rec.allocation_ids.mapped('payment_id').filtered(
                lambda p: p.state not in EXCLUDED_PAYMENT_STATES
            )

            if valid_payments:
                if all(p.state in PAID_PAYMENT_STATES for p in valid_payments):
                    rec.payment_state = 'paid'
                elif any(p.state in PAID_PAYMENT_STATES for p in valid_payments):
                    rec.payment_state = 'partial'
                else:
                    rec.payment_state = 'draft'
            else:
                rec.payment_state = False


    @api.depends('is_sale_proposal_vip')
    def _compute_vip_badge(self):
        for record in self:
            record.vip_badge = 'VIP' if record.is_sale_proposal_vip else ''

    @api.depends('sale_proposal_id.unit_id')
    def _compute_unit_id(self):
        for rec in self:
            rec.unit_id = rec.sale_proposal_id.unit_id.id if rec.sale_proposal_id else False

    @api.depends('sale_proposal_id.contract_type', 'reservation_id.contract_type')
    def _compute_contract_type(self):
        for rec in self:
            if rec.sale_proposal_id:
                rec.contract_type = rec.sale_proposal_id.contract_type
            elif rec.reservation_id:
                rec.contract_type = rec.reservation_id.contract_type
            else:
                rec.contract_type = False

    @api.depends('date', 'paid')
    def _compute_is_overdue(self):
        today = fields.Date.today()
        for rec in self:
            rec.is_overdue = not rec.paid and rec.date and rec.date < today
            if rec.is_overdue:
                rec.overdue_days = (today - rec.date).days
            else:
                rec.overdue_days = 0

    @api.model
    def _cron_recompute_overdue(self):
        unpaid = self.search([('paid', '=', False), ('date', '!=', False)])
        unpaid._compute_is_overdue()

        # Roll the stored "installments due to date" sum forward for any
        # contract in an active stage — the value depends on today's date,
        # so ORM dependency triggers alone are not enough.
        active_proposals = self.env['sale.proposal'].search([
            ('state', 'in', list(
                self.env['sale.proposal']._ACTIVE_CONTRACT_STATES_FOR_DUE
            )),
        ])
        if active_proposals:
            active_proposals._compute_installments_due_to_date_amount()

        sale_proposal_ids = unpaid.mapped('sale_proposal_id')
        if sale_proposal_ids:
            today = fields.Date.today()
            proposals_with_overdue = self.env['sale.proposal'].search([
                ('id', 'in', sale_proposal_ids.ids),
                ('installment_ids', '!=', False),
            ])
            for proposal in proposals_with_overdue:
                has_overdue_installment = any(
                    line.is_overdue for line in proposal.installment_ids
                )
                proposal.installment_payments_regular = not has_overdue_installment

            maintenance_model = self.env['maintenance.installment.lines']
            proposals_with_maintenance = self.env['sale.proposal'].search([
                ('id', 'in', sale_proposal_ids.ids),
                ('maintenance_installment_ids', '!=', False),
            ])
            unpaid_maintenance = maintenance_model.search([
                ('paid', '=', False),
                ('date', '!=', False),
                ('sale_proposal_id', 'in', sale_proposal_ids.ids),
            ])
            unpaid_maintenance._compute_is_overdue()

            for proposal in proposals_with_maintenance:
                has_overdue_maintenance = any(
                    line.is_overdue for line in proposal.maintenance_installment_ids
                )
                proposal.maintenance_payments_regular = not has_overdue_maintenance

    @api.depends('vat_id', 'amount')
    def calculate_total_amount(self):
        for rec in self:
            rec.total_amount = (rec.vat_id.amount / 100) * rec.amount + rec.amount

    # S6: base depends on payment paths only; sales_cheques redeclares with the cheque paths
    # added, calls super(), and extends _allocation_is_collected().
    @api.depends(
        'allocation_ids.allocated_amount',
        'allocation_ids.payment_id.state',
        'total_amount',
    )
    def _compute_paid_remaining(self):
        """
        Calculates paid and remaining amounts strictly through payment.allocation records.
        Filters ONLY for fully collected/paid states:
        - Payments: 'paid'
        - Cheques:  'done'
        """
        for rec in self:
            # Sum up strictly collected/paid allocations for THIS line
            direct_paid = 0.0
            for alloc in rec.allocation_ids:
                if rec._allocation_is_collected(alloc):
                    direct_paid += alloc.allocated_amount

            # Compute paid and remaining purely based on allocated records
            line_total = rec.total_amount or 0.0
            rec.paid_amount = min(line_total, direct_paid)
            rec.remaining_amount = max(0.0, line_total - rec.paid_amount)

    def _allocation_is_collected(self, alloc):
        """Delegates to payment.allocation._is_collected(), the one shared definition of
        "collected". Kept as a hook so call sites on this model read naturally."""
        return alloc._is_collected()

    def _has_cheque_allocation(self):
        """Whether any allocation on this line is a cheque. Base: never (no cheque module).
        sales_cheques overrides it."""
        return False

    @api.depends('remaining_amount', 'total_amount')
    def _compute_paid(self):
        """Auto-compute paid flag based on payment/cheque state"""
        for rec in self:
            if rec.remaining_amount <= 0.0 and rec.total_amount > 0:
                rec.paid = True
            elif not rec.paid:
                rec.paid = False

    def make_payment(self):
        """Create a payment record for cash or bank payment methods AND allocate it"""
        for line in self:
            # Check remaining amount
            if line.remaining_amount <= 0.0:
                raise ValidationError(_("This installment is already fully paid."))

            # Determine if this is an overseas contract
            is_overseas = line.sale_proposal_id.contract_type == 'overseas'

            proposal = line.sale_proposal_id
            reservation = line.reservation_id or (proposal.sale_contract_reservation_id if proposal else False)
            eoi = (proposal.eoi_id if proposal else False) or (reservation.eoi_id if reservation else False)

            # Create payment
            payment_vals = {
                'partner_id': line.sale_proposal_id.customer_id.id,
                'payment_type': 'inbound',
                'amount': line.remaining_amount,
                'currency_id': line.env.company.currency_id.id,
                'payment_method_type': line.sale_proposal_id.payment_methods if line.sale_proposal_id.payment_methods != 'cheque' else 'bank',
                'memo': f'{line.sale_proposal_id.name} - {line.name}',
                'installment_date': line.date,
                'sale_proposal_id': proposal.id if proposal else False,
                'sale_reservation_id': reservation.id if reservation else False,
                'eoi_id': eoi.id if eoi else False,
                'unit_id': line.unit_id.id if line.unit_id else False,
                'is_overseas': is_overseas,
                'overseas_payment_type': 'installment' if is_overseas else False,
                'from_contract': self.env.context.get('from_contract', False),
                'from_reservation': self.env.context.get('from_reservation', False),
            }

            # Filter journals based on payment method
            journal_domain = []
            if line.sale_proposal_id.payment_methods == 'cash':
                journal_domain.append(('type', '=', 'cash'))
            elif line.sale_proposal_id.payment_methods in ['bank', 'cheque']:
                journal_domain.append(('type', '=', 'bank'))

            journal = self.env['account.journal'].search(journal_domain, limit=1)
            if journal:
                payment_vals['journal_id'] = journal.id

            payment = self.env['account.payment'].with_context(
                {'payment_methods': line.sale_proposal_id.payment_methods}).create(payment_vals)

            # --- NEW: CREATE THE ALLOCATION RECORD! ---
            self.env['payment.allocation'].create({
                'payment_id': payment.id,
                'installment_id': line.id,
                'allocated_amount': line.remaining_amount
            })
            # ------------------------------------------

            # Mark payment method
            line.write({
                'payment_method_used': 'payment'
            })

        # Return form view for the created payment
        return {
            'name': _('Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'form',
            'res_id': payment.id,
            'target': 'current',
            'context': {'create': False},
        }

    def view_payment(self):
        """Open the associated payment records using the allocation table."""
        self.ensure_one()

        # Look through allocations to find the payments
        linked_payments = self.allocation_ids.mapped('payment_id')

        if not linked_payments:
            raise ValidationError(_("No payments have been allocated to this installment yet."))

        return {
            'name': _('Payments'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', linked_payments.ids)],
            'target': 'current',
            'context': {'create': False},
        }

    # make_cheque_payment() and view_cheque() moved to
    # isky_18_realestate_developer_sales_cheques (Phase 3 step 3): both are cheque features
    # and need the optional L1 cheque module.

    def _check_manual_paid_group(self):
        """Ticking Paid by hand is reserved to one group; the automatic tick is not affected
        because compute assignments never go through write()."""
        if not self.env.su and not self.env.user.has_group(MANUAL_PAID_GROUP):
            # `_` is shadowed by a local variable in write(), hence self.env._() here too.
            raise AccessError(self.env._(
                "Only users of the group 'Can Tick Installments as Paid' can tick or untick "
                "an installment as Paid."
            ))

    def action_mark_fully_paid(self):
        """Tick an installment that is only partly covered by payments: the difference is money
        settled outside the system, so it is written in the contract chatter."""
        self._check_manual_paid_group()
        for rec in self:
            if rec.paid:
                continue
            rec.with_context(mark_fully_paid=True).write({
                'paid': True,
                # S2: store date and user on the manual tick.
                'paid_date': fields.Datetime.now(),
                'paid_by_id': self.env.uid,
            })
            if rec.sale_proposal_id:
                # _message_log and not message_post: this only has to show up in the chatter, and
                # it must work for a user whose partner has no e-mail address.
                rec.sale_proposal_id._message_log(body=_(
                    "%(user)s marked installment %(name)s (due %(date)s) as fully paid: "
                    "%(paid)s registered out of %(amount)s, the rest is counted as settled "
                    "outside the system.",
                    user=self.env.user.name,
                    name=rec.name or '',
                    date=rec.date or '',
                    paid='{:,.2f}'.format(rec.paid_amount or 0.0),
                    amount='{:,.2f}'.format(rec.amount or 0.0),
                ))
        return True

    def write(self, vals):
        """Override write to trigger broker claim and commission checks when paid flag changes manually"""
        if 'paid' in vals and not self.env.su:
            new_paid = bool(vals['paid'])
            if any(record.paid != new_paid for record in self):
                self._check_manual_paid_group()

        if vals.get('paid') and not self.env.context.get('mark_fully_paid'):
            for record in self:
                if not record.paid and (record.paid_amount or 0.0) > 0.005:
                    raise ValidationError(self.env._(
                        "Installment %(name)s has %(paid)s registered out of %(amount)s. "
                        "Use the \"Mark fully paid\" button to count the rest as settled outside "
                        "the system, or register the remaining payment first.",
                        name=record.name or '',
                        paid='{:,.2f}'.format(record.paid_amount or 0.0),
                        amount='{:,.2f}'.format(record.amount or 0.0),
                    ))

        old_paid_states = {record.id: record.paid for record in self}
        sale_proposals_to_update = set()

        result = super(LoanLine, self).write(vals)

        # Only trigger if someone MANUALLY checks the 'paid' checkbox
        if 'paid' in vals:
            for record in self:
                if vals.get('paid') and not old_paid_states.get(record.id):
                    if record.sale_proposal_id:
                        sale_proposals_to_update.add(record.sale_proposal_id.id)

        # Process all affected sale proposals
        if sale_proposals_to_update:
            for proposal_id in sale_proposals_to_update:
                proposal = self.env['sale.proposal'].browse(proposal_id)

                if proposal._is_commission_eligible():
                    # Invalidate cache to force recomputation
                    proposal.invalidate_recordset(['total_collected_amount', 'collection_percentage'])

                    # Force recompute by accessing the computed fields
                    _ = proposal.total_collected_amount
                    _ = proposal.collection_percentage

                    # Manually trigger commission achievement creation
                    proposal._auto_create_commission_achievements()

                    # Check and create broker claim if threshold met
                    if proposal.referred_by == 'broker':
                        proposal._check_and_create_broker_claim()

                    # Check and create ambassador claim if threshold met
                    if proposal.referred_by == 'ambassador':
                        proposal._check_and_create_ambassador_claim()

        return result
