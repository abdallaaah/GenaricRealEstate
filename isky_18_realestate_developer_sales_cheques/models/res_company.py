from odoo import fields, models


class ResCompany(models.Model):
    """S8: cheque settings that belong to the company, not to ir.config_parameter.

    Company-level on purpose: a multi-company database needs a different incoming credit
    account per company, which a single global ir.config_parameter cannot express. The
    legacy cheque module's own account settings are config parameters - backlog #33 covers
    moving those to generic keys in Phase 7; these two start out correct instead."""
    _inherit = 'res.company'

    cheque_incoming_credit_account_id = fields.Many2one(
        'account.account',
        string='Incoming Cheque Credit Account',
        domain=[('deprecated', '=', False)],
        help="Credit account used for every incoming cheque this company creates. "
             "cheque.manage.credit_account is mandatory at the database level and no "
             "cheque-creating action supplies it, so without this setting creating a "
             "cheque fails. See backlog #34.")

    cheques_enabled = fields.Boolean(
        string='Generate Cheques from Deals',
        default=True,
        help="When off, no cheque is generated from a sale proposal. Manual cheque use - "
             "registering a cheque against an installment, a maintenance line, an EOI or a "
             "reservation - is unaffected.")
