from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MaintenanceInstallmentLines(models.Model):
    """Cheque side of maintenance.installment.lines. Phase 3 step 3, supplement S1."""
    _inherit = 'maintenance.installment.lines'

    cheque_ids = fields.One2many('cheque.manage', 'maintenance_installment_line_id', string="Cheques")
    allocated_cheque_ids = fields.Many2many(
        'cheque.manage',
        string='Allocated Cheques',
        compute='_compute_allocated_records'
    )

    # --- S6 compute extensions -------------------------------------------------------------
    @api.depends('allocation_ids.payment_id', 'allocation_ids.cheque_id')
    def _compute_allocated_records(self):
        super()._compute_allocated_records()
        for rec in self:
            rec.allocated_cheque_ids = rec.allocation_ids.mapped('cheque_id')

    @api.depends('allocation_ids.allocated_amount', 'allocation_ids.payment_id.state',
                 'allocation_ids.cheque_id.state', 'total_amount')
    def _compute_paid_remaining(self):
        return super()._compute_paid_remaining()

    @api.depends('allocation_ids.payment_id', 'allocation_ids.cheque_id')
    def _compute_payment_method_used(self):
        return super()._compute_payment_method_used()

    # --- hooks ----------------------------------------------------------------------------
    # _allocation_is_collected() is NOT overridden here: the base delegates to
    # payment.allocation._is_collected(), which this module already extends.

    def _has_cheque_allocation(self):
        self.ensure_one()
        return any(alloc.cheque_id for alloc in self.allocation_ids)

    # --- cheque actions, moved verbatim from sales_crm -------------------------------------
    def action_create_cheque(self):
        """Create a single cheque record for this maintenance installment line"""
        self.ensure_one()

        # Check remaining amount
        if self.remaining_amount <= 0.0:
            raise ValidationError(_("This maintenance installment is already fully paid."))

        if not self.sale_proposal_id:
            raise ValidationError(_("This maintenance installment is not linked to a sale proposal."))

        if not self.date:
            raise ValidationError(_("Please set a date for this maintenance installment before creating a cheque."))

        # Get the cheque journal from config
        journal_param = self.env["ir.config_parameter"].sudo().get_param("arkzayed_18_gt_cheque_management.journal_id")
        if not journal_param:
            raise ValidationError(_("Please configure the cheque journal in settings."))

        journal = self.env['account.journal'].browse(int(journal_param))
        if not journal.exists():
            raise ValidationError(_("The configured cheque journal does not exist."))

        proposal = self.sale_proposal_id
        reservation = self.reservation_id or (proposal.sale_contract_reservation_id if proposal else False)
        eoi = (proposal.eoi_id if proposal else False) or (reservation.eoi_id if reservation else False)

        # Create cheque
        cheque_vals = {
            'name': _('%s - %s') % (self.sale_proposal_id.name, self.name),
            'payer': self.sale_proposal_id.customer_id.id,
            'bank_id': self.sale_proposal_id.bank_id.id if self.sale_proposal_id.bank_id else False,
            'cheq_type': 'incoming',
            'amount': self.remaining_amount,
            'cheque_date': self.date,
            'cheque_receive_date': fields.Date.today(),
            'journal_id': journal.id,
            'state': 'draft',
            'description': self.name or '',
            'sale_proposal_id': proposal.id if proposal else False,
            'sale_reservation_id': reservation.id if reservation else False,
            'eoi_id': eoi.id if eoi else False,
            'unit_id': self.unit_id.id if self.unit_id else False,
            'source_type': 'maintenance',
            'from_contract': self.env.context.get('from_contract', False),
            'from_reservation': self.env.context.get('from_reservation', False),
        }

        cheque = self.env['cheque.manage'].create(cheque_vals)

        # ALLOCATE IT
        self.env['payment.allocation'].create({
            'cheque_id': cheque.id,
            'maintenance_id': self.id,
            'allocated_amount': self.remaining_amount
        })

        # mark payment method
        self.write({
            'payment_method_used': 'cheque'
        })

        # Trigger broker claim check
        if self.sale_proposal_id and self.sale_proposal_id.state == 'signed_client':
            self.sale_proposal_id._compute_collection_amounts()
            if self.sale_proposal_id.referred_by == 'broker':
                self.sale_proposal_id._check_and_create_broker_claim()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Cheque created successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_cheque(self):
        """View the cheque linked to this maintenance installment (via allocations)."""
        self.ensure_one()

        linked_cheques = self.allocation_ids.mapped('cheque_id')

        if not linked_cheques:
            raise ValidationError(_("No cheque has been allocated for this maintenance installment yet."))

        view_mode = 'form' if len(linked_cheques) == 1 else 'list,form'

        return {
            'name': _('Cheque'),
            'type': 'ir.actions.act_window',
            'res_model': 'cheque.manage',
            'view_mode': view_mode,
            'domain': [('id', 'in', linked_cheques.ids)],
            'res_id': linked_cheques[0].id if len(linked_cheques) == 1 else False,
            'target': 'current',
        }
