from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LoanLine(models.Model):
    """Cheque side of installment.lines. Phase 3 step 3, supplement S1: every field and every
    compute half that needs cheque.manage lives here, so sales_crm installs without the
    optional L1 cheque module."""
    _inherit = 'installment.lines'

    cheque_ids = fields.One2many('cheque.manage', 'installment_line_id', string="Cheques")
    cheque_state = fields.Char(string="Cheque State", compute="_compute_states")
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

    @api.depends('allocation_ids.payment_id', 'allocation_ids.cheque_id')
    def _compute_payment_method_used(self):
        return super()._compute_payment_method_used()

    @api.depends('allocation_ids.payment_id.state', 'allocation_ids.cheque_id.state')
    def _compute_states(self):
        """Fill cheque_state on top of the payment_state the base computes."""
        super()._compute_states()
        EXCLUDED_CHEQUE_STATES = ('cancel', 'return_to_client', 'bounce')
        DONE_CHEQUE_STATES = ('done',)
        for rec in self:
            valid_cheques = rec.allocation_ids.mapped('cheque_id').filtered(
                lambda c: c.state not in EXCLUDED_CHEQUE_STATES
            )
            if valid_cheques:
                if all(c.state in DONE_CHEQUE_STATES for c in valid_cheques):
                    rec.cheque_state = 'done'
                elif any(c.state in DONE_CHEQUE_STATES for c in valid_cheques):
                    rec.cheque_state = 'partial'
                else:
                    rec.cheque_state = 'draft'
            else:
                rec.cheque_state = False

    @api.depends(
        'allocation_ids.allocated_amount',
        'allocation_ids.payment_id.state',
        'allocation_ids.cheque_id.state',
        'total_amount',
    )
    def _compute_paid_remaining(self):
        return super()._compute_paid_remaining()

    # --- hooks ----------------------------------------------------------------------------
    # _allocation_is_collected() is NOT overridden here: the base delegates to
    # payment.allocation._is_collected(), which this module already extends with the cheque
    # case. Overriding it again would be a second copy of the same rule.

    def _has_cheque_allocation(self):
        self.ensure_one()
        return any(alloc.cheque_id for alloc in self.allocation_ids)

    # --- cheque actions, moved verbatim from sales_crm -------------------------------------
    def make_cheque_payment(self):
        """Create a cheque.manage record AND allocate it"""
        self.ensure_one()

        # Check remaining amount
        if self.remaining_amount <= 0.0:
            raise ValidationError(_("This installment is already fully paid."))

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
            'name': f'{self.sale_proposal_id.name} - {self.name}',
            'payer': self.sale_proposal_id.customer_id.id,
            'bank_id': self.sale_proposal_id.bank_id.id if self.sale_proposal_id.bank_id else False,
            'amount': self.remaining_amount,
            'cheque_date': self.date,
            'cheque_receive_date': fields.Date.today(),
            'state': 'draft',
            'cheq_type': 'incoming',
            'description': f'{self.sale_proposal_id.name} - {self.name}',
            'sale_proposal_id': proposal.id if proposal else False,
            'sale_reservation_id': reservation.id if reservation else False,
            'eoi_id': eoi.id if eoi else False,
            'unit_id': self.unit_id.id if self.unit_id else False,
            'journal_id': journal.id,
            'source_type': 'installment',
            'from_contract': self.env.context.get('from_contract', False),
            'from_reservation': self.env.context.get('from_reservation', False),
        }

        cheque = self.env['cheque.manage'].create(cheque_vals)

        # --- NEW: CREATE THE ALLOCATION RECORD! ---
        self.env['payment.allocation'].create({
            'cheque_id': cheque.id,
            'installment_id': self.id,
            'allocated_amount': self.remaining_amount
        })
        # ------------------------------------------

        # Mark payment method
        self.write({
            'payment_method_used': 'cheque'
        })

        # Return action to view the created cheque
        return {
            'name': _('Cheque'),
            'view_mode': 'form',
            'res_model': 'cheque.manage',
            'res_id': cheque.id,
            'type': 'ir.actions.act_window',
            'context': {'create': False},
        }

    def view_cheque(self):
        """Open the associated cheque records using the allocation table."""
        self.ensure_one()

        # Look through allocations to find the cheques
        linked_cheques = self.allocation_ids.mapped('cheque_id')

        if not linked_cheques:
            raise ValidationError(_("No cheques have been allocated to this installment yet."))

        return {
            'name': _('Cheques'),
            'view_mode': 'list,form',
            'res_model': 'cheque.manage',
            'domain': [('id', 'in', linked_cheques.ids)],
            'type': 'ir.actions.act_window',
            'context': {'create': False},
        }
