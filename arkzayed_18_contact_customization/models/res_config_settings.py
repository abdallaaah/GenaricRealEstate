import json
from odoo import api, fields, models
class ResConfigSettings(models.TransientModel):

    _inherit = 'res.config.settings'

    contact_default_account_receivable_id = fields.Many2one(
        comodel_name='account.account',
        string="Account Receivable",
        domain="[('account_type', '=', 'asset_receivable'), ('deprecated', '=', False)]",
        help="Default receivable account applied to new contacts when no value is set.",
    )

    contact_default_account_payable_id = fields.Many2one(
        comodel_name='account.account',
        string="Account Payable",
        domain="[('account_type', '=', 'liability_payable'), ('deprecated', '=', False)]",
        help="Default payable account applied to new contacts when no value is set.",
    )

    contact_default_account_down_payment_receivable_id = fields.Many2one(
        comodel_name='account.account',
        string="Account Down Payment Receivable",
        domain="[('deprecated', '=', False), ('reconcile','=',True)]",
        help="Default down-payment receivable account applied to new contacts.",
    )

    contact_default_account_down_payment_payable_id = fields.Many2one(
        comodel_name='account.account',
        string="Account Down Payment Payable",
        domain="[('deprecated', '=', False), ('reconcile','=',True)]",
        help="Default down-payment payable account applied to new contacts.",
    )

    contact_default_property_notes_receivable_id = fields.Many2one(
        comodel_name='account.account',
        string="Notes Receivable Account",
        domain="[('deprecated', '=', False)]",
        help="Default notes receivable account applied to new contacts.",
    )

    _CONTACT_DEFAULTS_MAP = {
        'contact_default_account_receivable_id':'property_account_receivable_id',
        'contact_default_account_payable_id': 'property_account_payable_id',
        'contact_default_account_down_payment_receivable_id': 'property_account_down_payment_receivable_id',
        'contact_default_account_down_payment_payable_id':'property_account_down_payment_payable_id',
        'contact_default_property_notes_receivable_id':'property_notes_receivable_account_id',
    }
    @api.model
    def get_values(self):
        res = super().get_values()

        IrDefault = self.env['ir.default'].sudo()
        IrModelFields = self.env['ir.model.fields'].sudo()
        company_id = self.env.company.id

        def _get_default(field_name):
            ir_field = IrModelFields._get('res.partner', field_name)
            if not ir_field:
                return False
            default = IrDefault.search([
                ('field_id', '=', ir_field.id),
                ('user_id', '=', False),
                ('company_id', '=', company_id),
                ('condition', '=', False),
            ], limit=1)
            return json.loads(default.json_value) if default else False

        for settings_field, partner_field in self._CONTACT_DEFAULTS_MAP.items():
            res[settings_field] = _get_default(partner_field) or False

        return res


    def set_values(self):
        super().set_values()

        IrDefault = self.env['ir.default'].sudo()
        company_id = self.env.company.id

        for settings_field, partner_field in self._CONTACT_DEFAULTS_MAP.items():
            account = getattr(self, settings_field)
            IrDefault.set(
                'res.partner',
                partner_field,
                account.id or False,
                user_id=False,
                company_id=company_id,
            )