from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    """Returned-cheque half of account.payment. Phase 3 step 4, supplement S1."""
    _inherit = 'account.payment'

    cheque_id = fields.Many2one(
        'cheque.manage',
        string='Cheque',
        copy=False,
        tracking=True
    )
    returned_cheque_ids = fields.Many2many(
        'cheque.manage',
        'account_payment_returned_cheque_rel',
        'payment_id', 'cheque_id',
        string='Returned Cheques',
        copy=False,
        tracking=True
    )
    returned_source_type = fields.Selection(
        [('installment', 'Installment'), ('maintenance', 'Maintenance')],
        string='Returned Source Type'
    )

    # --- S6 compute extension --------------------------------------------------------------

    @api.depends(
        'installment_line_id.sale_proposal_id.contract_type',
        'maintenance_installment_line_id.sale_proposal_id.contract_type',
        'sale_proposal_id.contract_type',
        'returned_cheque_ids.sale_proposal_id.contract_type',
    )
    def _compute_contract_type(self):
        return super()._compute_contract_type()

    # --- hooks declared in sales_crm -------------------------------------------------------

    def _returned_cheque_proposal(self):
        res = super()._returned_cheque_proposal()
        if res or not self.returned_cheque_ids:
            return res
        proposals = self.returned_cheque_ids.mapped('sale_proposal_id').filtered(lambda p: p)
        return proposals[0] if len(proposals) == 1 else False

    def _mark_returned_cheques_paid(self):
        super()._mark_returned_cheques_paid()
        if self.is_returned_cheque and self.returned_cheque_ids:
            self.returned_cheque_ids.write({
                'is_returned_paid': True,
                'returned_payment_id': self.id,
            })

    # --- cheque-only validation ------------------------------------------------------------

    @api.onchange('returned_cheque_ids')
    def _onchange_returned_source_type(self):
        for rec in self:
            types = set(rec.returned_cheque_ids.mapped('source_type'))
            types.discard(False)

            if len(types) == 1:
                rec.returned_source_type = list(types)[0]
            else:
                rec.returned_source_type = False

    @api.constrains('is_returned_cheque', 'returned_cheque_ids')
    def _check_returned_cheques_same_type(self):
        for rec in self:
            if rec.is_returned_cheque and rec.returned_cheque_ids:
                types = set(rec.returned_cheque_ids.mapped('source_type'))
                types.discard(False)
                if len(types) > 1:
                    raise ValidationError(
                        _("You can't mix Installment and Maintenance cheques in the same returned payment."))
