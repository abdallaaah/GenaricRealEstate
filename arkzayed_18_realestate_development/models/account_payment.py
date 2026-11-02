# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    is_returned_cheque = fields.Boolean(
        string='Is Returned Cheque',
        default=False,
        help='Flag to indicate if this payment is for a returned cheque that requires collection entry'
    )
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
