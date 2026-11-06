from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PaymentAllocation(models.Model):
    """Cheque side of payment.allocation. Phase 3 step 3, supplement S1."""
    _inherit = 'payment.allocation'

    cheque_id = fields.Many2one('cheque.manage', string='Cheque', ondelete='cascade', tracking=True)

    def _is_collected(self):
        """A cheque in state 'done' also counts as collected."""
        if super()._is_collected():
            return True
        return bool(self.cheque_id) and self.cheque_id.state == 'done'

    def _fund_kind(self):
        return super()._fund_kind() or ('cheque' if self.cheque_id else False)

    def _allocation_parent(self):
        """An allocation can hang off a cheque instead of a payment."""
        self.ensure_one()
        return super()._allocation_parent() or self.cheque_id

    # S6: redeclare with this module's own path added, then call super().
    @api.constrains('payment_id', 'cheque_id', 'installment_id', 'maintenance_id')
    def _check_unique_allocation_line(self):
        super()._check_unique_allocation_line()
        if self.env.context.get('skip_allocation_check'):
            return
        for rec in self:
            if not rec.cheque_id:
                continue
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
