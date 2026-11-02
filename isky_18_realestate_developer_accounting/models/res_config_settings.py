from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # --- from arkzayed_18_realestate_development/models/res_config_settings.py ---
    # Overseas Payment Accounts (used by account_payment._prepare_move_line_default_vals,
    # which now lives in this module's account_payment.py)
    overseas_installment_account = fields.Many2one(
        'account.account',
        string='Overseas Installment Account',
        config_parameter='arkzayed_18_realestate_development.overseas_installment_account',
        domain=[('deprecated', '=', False)],
        help="Credit account for overseas installment payments"
    )
    overseas_maintenance_account = fields.Many2one(
        'account.account',
        string='Overseas Maintenance Account',
        config_parameter='arkzayed_18_realestate_development.overseas_maintenance_account',
        domain=[('deprecated', '=', False)],
        help="Credit account for overseas maintenance payments"
    )

    income_account = fields.Many2one("account.account", "Income Account",
                                     config_parameter="arkzayed_18_realestate_development.income_account")
    service_account_id = fields.Many2one("account.account", "Service Account",
                                         config_parameter="arkzayed_18_realestate_development.service_account")
    market_fees_account_id = fields.Many2one("account.account", "Market Fees Account",
                                             config_parameter="arkzayed_18_realestate_development.market_fees_account")
    maintenance_account_id = fields.Many2one(
        'account.account',
        string='Maintenance Account',
        config_parameter='arkzayed_18_realestate_development.maintenance_account_id',
        domain=[('deprecated', '=', False)],
        help="Account used for maintenance revenue when delivering contracts"
    )
    deferred_revenue_overseas_account = fields.Many2one(
        'account.account',
        string='Deferred Revenue for Overseas',
        config_parameter='arkzayed_18_realestate_development.deferred_revenue_overseas_account',
        domain=[('deprecated', '=', False)],
        help="Account used for deferred revenue on overseas contracts when signed by client"
    )

    penalty_debit_account_id = fields.Many2one(
        'account.account',
        string='Penalty Debit Account',
        config_parameter='arkzayed_18_realestate_development.penalty_debit_account_id',
        domain=[('deprecated', '=', False)],
        help="Account to debit when creating penalty entries (e.g., Accounts Receivable)"
    )
    penalty_credit_account_id = fields.Many2one(
        'account.account',
        string='Penalty Credit Account',
        config_parameter='arkzayed_18_realestate_development.penalty_credit_account_id',
        domain=[('deprecated', '=', False)],
        help="Account to credit when creating penalty entries (e.g., Penalty Income)"
    )
    penalty_journal_id = fields.Many2one(
        'account.journal',
        string='Penalty Journal',
        config_parameter='arkzayed_18_realestate_development.penalty_journal_id',
        domain=[('type', '=', 'general')],
        help="Journal used for penalty entries"
    )

    # Cancellation Penalty
    cancellation_penalty_account_id = fields.Many2one(
        'account.account',
        string='Cancellation Penalty Account',
        config_parameter='arkzayed_18_realestate_development.cancellation_penalty_account_id',
        domain=[('deprecated', '=', False)],
        help="Account for cancellation penalty (used as destination account in refund payment)"
    )

    #cancellation refund accounts
    cancellation_refund_debit_account_id = fields.Many2one(
        'account.account',
        string='Cancellation Refund Debit Account',
        config_parameter='arkzayed_18_realestate_development.cancellation_refund_debit_account_id',
        domain=[('deprecated', '=', False)],
        help="Account to debit when creating penalty entries (e.g., Accounts Receivable)"
    )
    cancellation_refund_credit_account_id = fields.Many2one(
        'account.account',
        string='Cancellation Refund Credit Account',
        config_parameter='arkzayed_18_realestate_development.cancellation_refund_credit_account_id',
        domain=[('deprecated', '=', False)],
        help="Account to credit when creating penalty entries (e.g., Penalty Income)"
    )
    cancellation_refund_journal_id = fields.Many2one(
        'account.journal',
        string='Cancellation Refund Journal',
        config_parameter='arkzayed_18_realestate_development.cancellation_refund_journal_id',
        domain=[('type', '=', 'general')],
        help="Journal used for Cancellation Refund entries"
    )

    broker_commission_debit_account_id = fields.Many2one(
        'account.account',
        string='Broker Commission Debit Account',
        config_parameter='arkzayed_18_realestate_development.commission_debit_account_id',
        help='Debit account for broker commission journal entries (Expense Account)'
    )
    broker_commission_credit_account_id = fields.Many2one(
        'account.account',
        string='Broker Commission Credit Account',
        config_parameter='arkzayed_18_realestate_development.commission_credit_account_id',
        help='Credit account for broker commission journal entries (Liability/Payable Account)'
    )
    broker_commission_journal_id = fields.Many2one(
        'account.journal',
        string='Broker Commission Journal',
        config_parameter='arkzayed_18_realestate_development.commission_journal_id',
        domain=[('type', '=', 'general')],
        help='Journal for broker commission entries'
    )

    sale_commission_debit_account_id = fields.Many2one(
        'account.account',
        string='Sale Commission Debit Account',
        config_parameter='arkzayed_18_realestate_development.sale_commission_debit_account_id',
        help='Debit account for sale commission journal entries (Expense Account)'
    )
    sale_commission_credit_account_id = fields.Many2one(
        'account.account',
        string='Sale Commission Credit Account',
        config_parameter='arkzayed_18_realestate_development.sale_commission_credit_account_id',
        help='Credit account for sale commission journal entries (Liability/Payable Account)'
    )
    sale_commission_journal_id = fields.Many2one(
        'account.journal',
        string='Sale Commission Journal',
        config_parameter='arkzayed_18_realestate_development.sale_commission_journal_id',
        domain=[('type', '=', 'general')],
        help='Journal for broker commission entries'
    )
