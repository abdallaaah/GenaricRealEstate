import calendar
import datetime
from datetime import date, datetime, timedelta

from odoo.addons.isky_18_realestate_developer_unit_inventory.models.selections import contract_type_selection
from odoo import api, fields, models
from odoo.exceptions import UserError, AccessError, ValidationError
from odoo.tools.translate import _


class MaintenanceInstallmentLines(models.Model):
    _name = "maintenance.installment.lines"
    _description = "Maintenance Installment"
    _order = "serial"

    name = fields.Char("Name")
    date = fields.Date("Date")
    serial = fields.Integer("#")
    amount = fields.Float("Payment", digits=(16, 4))
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)
    total_amount = fields.Float("Total Amount", compute='calculate_total_amount', digits=(16, 4))
    paid_amount = fields.Float(
        "Paid Amount",
        compute='_compute_paid_remaining',
        store=True,
        digits=(16, 4),
        help="Amount actually collected for this maintenance installment."
    )
    remaining_amount = fields.Float(
        "Remaining Amount",
        compute='_compute_paid_remaining',
        store=True,
        digits=(16, 4),
        help="Outstanding amount still to be collected."
    )
    payment_ids = fields.One2many('account.payment', 'maintenance_installment_line_id', string="Payments")
    # cheque_ids moved to isky_18_realestate_developer_sales_cheques (Phase 3 step 3).

    reservation_id = fields.Many2one("real.estate.sale.reservation", "", ondelete="cascade", readonly=True)
    sale_proposal_id = fields.Many2one("sale.proposal", ondelete="cascade", readonly=True)
    is_sale_proposal_vip = fields.Boolean(related="sale_proposal_id.is_vip")
    vip_badge = fields.Char(string='VIP', compute='_compute_vip_badge', store=True)

    partner_id = fields.Many2one('res.partner', string="Partner")
    unit_id = fields.Many2one('real.estate.unit', string="Unit", compute='_compute_unit_id', store=True)
    contract_type = fields.Selection(selection=contract_type_selection, compute='_compute_contract_type', store=True)

    @api.depends('is_sale_proposal_vip')
    def _compute_vip_badge(self):
        for record in self:
            record.vip_badge = 'VIP' if record.is_sale_proposal_vip else ''

    @api.depends('sale_proposal_id.contract_type', 'reservation_id.contract_type')
    def _compute_contract_type(self):
        for rec in self:
            if rec.sale_proposal_id:
                rec.contract_type = rec.sale_proposal_id.contract_type
            elif rec.reservation_id:
                rec.contract_type = rec.reservation_id.contract_type
            else:
                rec.contract_type = False
    journal_id = fields.Many2one('account.journal')
    invoice_id = fields.Many2one("account.move", string="Invoice")
    payment_state = fields.Selection(related="invoice_id.payment_state", readonly=True, string="Payment State")
    invoice_state = fields.Selection(related="invoice_id.state", readonly=True)
    amount_residual = fields.Monetary(related="invoice_id.amount_residual", readonly=True)
    currency_id = fields.Many2one(related="invoice_id.currency_id", readonly=True)
    tax_ids = fields.Many2many("account.tax", string="Tax")
    vat_id = fields.Many2one("account.tax", string="Vat")

    payment_method_used = fields.Selection([
        ('payment', 'Payment'),
        ('cheque', 'Cheque'),
        ('both', 'Payment & Cheque'),
    ], string='Payment Method Used', compute='_compute_payment_method_used', store=True)

    paid = fields.Boolean(
        "Paid",
        compute='_compute_paid',
        store=True,
        readonly=False,
        help="Automatically set to True when payment is posted or cheque is done. Can be manually set."
    )

    @api.depends('remaining_amount', 'total_amount')
    def _compute_paid(self):
        """Auto-compute paid flag based on remaining amount"""
        for rec in self:
            if rec.remaining_amount <= 0.0 and rec.total_amount > 0:
                rec.paid = True
            elif not rec.paid:
                rec.paid = False

    is_overdue = fields.Boolean(compute='_compute_is_overdue', store=True)
    overdue_days = fields.Integer(string="Overdue Days", compute='_compute_is_overdue', store=True)

    allocation_ids = fields.One2many('payment.allocation', 'maintenance_id', string='Allocations')

    allocated_payment_ids = fields.Many2many(
        'account.payment',
        string='Allocated Payments',
        compute='_compute_allocated_records'
    )
    # allocated_cheque_ids moved to isky_18_realestate_developer_sales_cheques.

    # S6: base depends on payment paths only; sales_cheques adds the cheque paths.
    @api.depends('allocation_ids.payment_id')
    def _compute_allocated_records(self):
        for rec in self:
            rec.allocated_payment_ids = rec.allocation_ids.mapped('payment_id')

    # S6: base depends on payment paths only; sales_cheques redeclares with the cheque paths
    # added and extends _allocation_is_collected().
    @api.depends('allocation_ids.allocated_amount', 'allocation_ids.payment_id.state',
                 'total_amount')
    def _compute_paid_remaining(self):
        for rec in self:
            paid = 0.0
            for alloc in rec.allocation_ids:
                if rec._allocation_is_collected(alloc):
                    paid += alloc.allocated_amount

            rec.paid_amount = min(rec.total_amount, paid)
            rec.remaining_amount = max(0.0, rec.total_amount - rec.paid_amount)

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

    @api.depends('date', 'paid')
    def _compute_is_overdue(self):
        today = fields.Date.today()
        for rec in self:
            rec.is_overdue = not rec.paid and rec.date and rec.date < today
            if rec.is_overdue:
                rec.overdue_days = (today - rec.date).days
            else:
                rec.overdue_days = 0

    @api.depends('vat_id', 'amount')
    def calculate_total_amount(self):
        for rec in self:
            rec.total_amount = (rec.vat_id.amount / 100) * rec.amount + rec.amount

    def _allocation_is_collected(self, alloc):
        """Delegates to payment.allocation._is_collected(), the one shared definition of
        "collected"."""
        return alloc._is_collected()

    def _has_cheque_allocation(self):
        """Base: no cheque module, so never. sales_cheques overrides it."""
        return False

    @api.depends('sale_proposal_id')
    def _compute_unit_id(self):
        for rec in self:
            rec.unit_id = rec.sale_proposal_id.unit_id.id if rec.sale_proposal_id else False

    # action_create_cheque() and action_view_cheque() moved to
    # isky_18_realestate_developer_sales_cheques (Phase 3 step 3).

    def action_create_payment(self):
        """Create a payment record for maintenance installment"""
        self.ensure_one()

        # Check remaining amount
        if self.remaining_amount <= 0.0:
            raise ValidationError(_("This maintenance installment is already fully paid."))

        if not self.sale_proposal_id:
            raise ValidationError(_("This maintenance installment is not linked to a sale proposal."))

        if not self.date:
            raise ValidationError(_("Please set a date for this maintenance installment before creating a payment."))

        # Determine if this is an overseas contract
        is_overseas = self.sale_proposal_id.contract_type == 'overseas'

        proposal = self.sale_proposal_id
        reservation = self.reservation_id or (proposal.sale_contract_reservation_id if proposal else False)
        eoi = (proposal.eoi_id if proposal else False) or (reservation.eoi_id if reservation else False)

        # Create payment
        payment_vals = {
            'partner_id': self.sale_proposal_id.customer_id.id,
            'payment_type': 'inbound',
            'amount': self.remaining_amount,
            'currency_id': self.env.company.currency_id.id,
            'payment_method_type': 'bank',
            'memo': f'{self.sale_proposal_id.name} - {self.name}',
            'date': fields.Date.today(),
            'sale_proposal_id': proposal.id if proposal else False,
            'sale_reservation_id': reservation.id if reservation else False,
            'eoi_id': eoi.id if eoi else False,
            'unit_id': self.unit_id.id if self.unit_id else False,
            'is_overseas': is_overseas,
            'overseas_payment_type': 'maintenance' if is_overseas else False,
            'from_contract': self.env.context.get('from_contract', False),
            'from_reservation': self.env.context.get('from_reservation', False),
        }

        # Get bank journal
        journal = self.env['account.journal'].search([('type', '=', 'bank')], limit=1)
        if journal:
            payment_vals['journal_id'] = journal.id

        payment = self.env['account.payment'].create(payment_vals)

        # ALLOCATE IT
        self.env['payment.allocation'].create({
            'payment_id': payment.id,
            'maintenance_id': self.id,
            'allocated_amount': self.remaining_amount
        })

        # mark payment method
        self.write({
            'payment_method_used': 'payment'
        })

        # Return form view
        return {
            'name': _('Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'form',
            'res_id': payment.id,
            'target': 'current',
            'context': {'create': False},
        }

    def action_view_payment(self):
        """View the payment linked to this maintenance installment (via allocations)."""
        self.ensure_one()

        linked_payments = self.allocation_ids.mapped('payment_id')

        if not linked_payments:
            raise ValidationError(_("No payment has been allocated for this maintenance installment yet."))

        view_mode = 'form' if len(linked_payments) == 1 else 'list,form'

        return {
            'name': _('Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': view_mode,
            'domain': [('id', 'in', linked_payments.ids)],
            'res_id': linked_payments[0].id if len(linked_payments) == 1 else False,
            'target': 'current',
        }

    def make_invoice(self):
        """
        Legacy method kept for backward compatibility
        Creates an invoice for the maintenance installment
        """
        move_obj = self.env['account.move']
        journal_pool = self.env["account.journal"]

        if not move_obj.check_access('create', False):
            try:
                self.check_access('write')
                self.check_access('write')
            except AccessError:
                raise UserError("You have been not access to create or edit invoice")

        for rec in self:
            if not rec.sale_proposal_id.customer_id.property_account_receivable_id:
                raise UserError(_("Please set receivable account for partner!"))
            if not rec.sale_proposal_id.account_income:
                raise UserError(_("Please set income account for this contract!"))

            journal = journal_pool.search([("type", "=", "sale")], limit=1)
            inv_dict = {
                "move_type": "out_invoice",
                "journal_id": journal.id,
                "partner_id": rec.sale_proposal_id.customer_id.id,
                "installment_lines_line_id": rec.id,
                "invoice_date_due": rec.date,
                "ref": (rec.sale_proposal_id.name + " - " + rec.name),
                "currency_id": self.env.company.currency_id.id,
                "invoice_user_id": self.env.user.id,
                "company_id": self.env.company.id,
                "invoice_line_ids": [],
            }

            line_vals = {
                "name": (rec.sale_proposal_id.name + " - " + rec.name),
                "quantity": 1,
                "price_unit": rec.total_amount,
            }
            if rec.vat_id:
                line_vals.update({"tax_ids": [(6, 0, [rec.vat_id.id])]})

            inv_dict["invoice_line_ids"] = [
                (
                    0,
                    None,
                    line_vals
                )
            ]

            invoice = move_obj.create(inv_dict)
            self.invoice_id = invoice.id

    def view_invoice(self):
        """View the invoice linked to this maintenance installment"""
        move = (self.env["account.move"].sudo().search([("installment_lines_line_id", "=", self.id)]))
        return {
            "name": _("Invoice"),
            "view_type": "form",
            "res_id": move.id,
            "view_mode": "form",
            "res_model": "account.move",
            "type": "ir.actions.act_window",
            "target": "current",
        }