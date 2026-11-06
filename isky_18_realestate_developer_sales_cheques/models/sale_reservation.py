from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleReservation(models.Model):
    """Cheque half of real.estate.sale.reservation. Moved out of sales_crm in Phase 3 step 3
    (supplement S1). Every compute here follows the S6 guard pattern: redeclare @api.depends
    with the cheque paths added, then call super()."""
    _inherit = 'real.estate.sale.reservation'

    cheque_manage_ids = fields.One2many('cheque.manage', 'sale_reservation_id', string='Cheque')

    # Bank Cheque: only feed create_cheque_payment() below.
    bank_cheque_journal = fields.Many2one('account.journal', string='Bank Journal', domain=[('type', '=', 'bank')])
    cheque_number = fields.Char()
    cheque_due_date = fields.Date()

    # --- S6 compute extensions -------------------------------------------------------------

    @api.depends('account_payment_ids', 'account_payment_ids.state',
                 'cheque_manage_ids', 'cheque_manage_ids.state')
    def _compute_is_payment_checked(self):
        res = super()._compute_is_payment_checked()
        for rec in self:
            if rec.is_payment_checked:
                continue
            matching_cheques = rec.cheque_manage_ids.filtered(
                lambda c: c.state not in ['draft', 'return_to_client', 'return', 'cancel'] and c.from_down_payment == True
            )
            if matching_cheques:
                rec.is_payment_checked = True
        return res

    @api.depends(
        'eoi_id',
        'eoi_id.account_payment_ids.state',
        'eoi_id.account_payment_ids.amount',
        'eoi_id.account_payment_ids.payment_type',
        'eoi_id.cheque_manage_ids.state',
        'eoi_id.cheque_manage_ids.amount',
        'eoi_id.cheque_manage_ids.cheq_type',
    )
    def _compute_eoi_amount(self):
        return super()._compute_eoi_amount()

    @api.depends('down_payment',
                 'account_payment_ids.amount', 'account_payment_ids.state',
                 'cheque_manage_ids.amount', 'cheque_manage_ids.state')
    def _compute_remaining_payment_amount(self):
        return super()._compute_remaining_payment_amount()

    # --- cheque hooks declared in sales_crm ------------------------------------------------

    def _eoi_cheque_amount(self):
        if not self.eoi_id:
            return 0.0
        valid_cheques = self.eoi_id.cheque_manage_ids.filtered(
            lambda c: c.cheq_type == 'incoming' and c.state not in ('cancel', 'return_to_client',
                                                                    'return', 'bounce') and c.from_eoi == True
        )
        return sum(valid_cheques.mapped('amount'))

    def _registered_cheque_amount(self):
        # Draft cheques are deliberately INCLUDED so the remaining amount drops as soon as
        # the user registers one.
        valid_cheques = self.cheque_manage_ids.filtered(
            lambda c: c.state not in ('return_to_client', 'return', 'cancel', 'bounce')
        )
        return sum(valid_cheques.mapped('amount'))

    def _checked_cheque_amount(self):
        matching_cheques = self.cheque_manage_ids.filtered(
            lambda c: c.state not in ['draft', 'return_to_client']
        )
        return sum(matching_cheques.mapped('amount')) if matching_cheques else 0

    def _contract_valid_cheques(self):
        return self.cheque_manage_ids.filtered(
            lambda c: c.state not in ('return_to_client', 'return', 'cancel', 'bounce')
        )

    def _contract_cheque_amount(self):
        return sum(self._contract_valid_cheques().mapped('amount'))

    def _link_eoi_cheques(self):
        super()._link_eoi_cheques()
        for cheque in self.eoi_id.cheque_manage_ids:
            cheque.sale_reservation_id = self.id

    def _link_cheques_to_contract(self, contract_id):
        super()._link_cheques_to_contract(contract_id)
        if self.cheque_manage_ids:
            self.cheque_manage_ids.write({'sale_proposal_id': contract_id.id})

    def _allocate_cheques_to_line(self, line, Allocation):
        super()._allocate_cheques_to_line(line, Allocation)
        valid_cheques = self._contract_valid_cheques()
        if not valid_cheques:
            return
        for chq in valid_cheques:
            if not Allocation.search([('cheque_id', '=', chq.id), ('installment_id', '=', line.id)]):
                Allocation.create({
                    'cheque_id': chq.id,
                    'installment_id': line.id,
                    'allocated_amount': chq.amount
                })
        line.write({'payment_method_used': 'cheque'})

    def _cheque_fund_entries(self):
        entries = super()._cheque_fund_entries()
        active_cheques = self.cheque_manage_ids.filtered(
            lambda c: c.state in ('register', 'collect', 'done', 'under_collection', 'return', 'bounce')
        )
        for c in active_cheques:
            entries.append({
                'type': 'cheque',
                'alloc_field': 'cheque_id',
                'record': c,
                'date': c.cheque_date or c.cheque_receive_date or fields.Date.today(),
                'remaining_pool': c.amount
            })
        return entries

    # --- cheque-only actions ---------------------------------------------------------------

    def create_cheque_payment(self):
        """Create cheque payment AND allocate to Down Payment line"""
        self.ensure_one()
        if not self.installment_ids or not self.maintenance_installment_ids:
            raise ValidationError(_('Please create installment and maintenance installment first.'))
        if not self.payment_attachment:
            raise ValidationError(_("Please upload the Payment Attachment before creating a cheque payment."))

        # Security Block
        if self.remaining_payment_amount <= 0.0:
            raise ValidationError(_("There is no remaining amount to be paid for this reservation."))

        journal = self.bank_cheque_journal

        if not journal:
            # Get the first available journal for cheque
            journal = self.env['account.journal'].search([], limit=1)

        if not journal:
            raise ValidationError(_("No journal found. Please create one first."))

        # Automatically set the amount to the exact remaining balance
        amount = self.remaining_payment_amount
        amount = self._apply_rounding_config(amount)

        cheque_payment_id = self.env['cheque.manage'].create({
            'payer': self.customer_id.id,
            'amount': amount,
            'sale_reservation_id': self.id,
            'eoi_id': self.eoi_id.id if self.eoi_id else False,
            'unit_id': self.unit_id.id if self.unit_id else False,
            'journal_id': journal.id,
            'cheq_type': 'incoming',
            'from_down_payment': True,
            'from_reservation': True,
        })
        if self.cheque_due_date:
            cheque_payment_id.cheque_date = self.cheque_due_date

        if self.cheque_number:
            cheque_payment_id.cheque_no = self.cheque_number

        # --- ALLOCATE TO DOWN PAYMENT INSTALLMENT LINE ---
        dp_lines = self.installment_ids.filtered(
            lambda l: l.is_down_payment or l.is_down_payment_reservation or (l.name and 'Down Payment' in l.name)
        )
        if dp_lines:
            dp_line = dp_lines[0]
            self.env['payment.allocation'].create({
                'cheque_id': cheque_payment_id.id,
                'installment_id': dp_line.id,
                'allocated_amount': cheque_payment_id.amount,
            })
            dp_line.write({'payment_method_used': 'cheque'})
        # -------------------------------------------------
        return {
            'name': _('Cheque Payment'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'cheque.manage',
            'res_id': cheque_payment_id.id,
            'type': 'ir.actions.act_window',
            'target': 'current',
        }

    def action_show_cheques(self):
        """Show cheques for this reservation"""
        cheques = self.env['cheque.manage'].search([('sale_reservation_id', '=', self.id)])
        if cheques:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'cheque.manage',
                'name': _("Cheques"),
                'target': 'current',
                'views': [(False, 'list'), (False, 'form')],
                'domain': [('sale_reservation_id', '=', self.id)],
                'context': {
                    'default_cheq_type': 'incoming',
                    'default_sale_reservation_id': self.id,
                    'default_amount': self.reservation_amount,
                    'default_payer': self.customer_id.id
                }
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'cheque.manage',
                'name': _("Cheques"),
                'target': 'current',
                'views': [(False, 'form'), (False, 'list')],
                'context': {
                    'default_cheq_type': 'incoming',
                    'default_sale_reservation_id': self.id,
                    'default_amount': self.reservation_amount,
                    'default_payer': self.customer_id.id
                }
            }
