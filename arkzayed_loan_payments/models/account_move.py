from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    # NOTE: deliberately NOT named 'loan_id' — account_loans core already defines a related
    # field with that exact name (related='generating_loan_line_id.loan_id'); reusing the name
    # collided with it instead of replacing it, so settlement AND accrual moves both matched.
    settlement_loan_id = fields.Many2one(
        'account.loan', string='Loan (Settlement)', readonly=True, copy=False,
        help="Set only on the settlement entry created by the loan's 'Register Payment' wizard "
             "(not on the automatic accrual/reclassification entries).",
    )
    is_loan_commission_accrual = fields.Boolean(
        default=False, copy=False,
        help="True only on the Commission accrual entry generated per loan line, "
             "so it can be settled separately from the core Principal & Interest entry.",
    )
