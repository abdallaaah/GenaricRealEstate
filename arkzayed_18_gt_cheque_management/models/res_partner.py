from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    property_account_down_payment_receivable_id = fields.Many2one(
        'account.account',
        string="Account Down Payment Receivable",
        domain="[('deprecated', '=', False), ('reconcile','=',True)]",
        help="This account will be used instead of the default one as the down payment receivable account for the current partner",
    )

    property_account_down_payment_payable_id = fields.Many2one(
        'account.account',
        string="Account Down Payment Payable",
        domain="[('deprecated', '=', False), ('reconcile','=',True)]",
        help="This account will be used instead of the default one as the down payment payable account for the current partner",
    )

    property_notes_receivable_account_id = fields.Many2one('account.account', string='Notes Receivable Account',)

    @api.model
    def default_get(self, fields_list):
        """Override default_get to inherit parent's down payment accounts"""
        defaults = super(ResPartner, self).default_get(fields_list)

        # Check if we have a parent_id in the context or defaults
        parent_id = self.env.context.get('default_parent_id') or defaults.get('parent_id')

        if parent_id:
            parent = self.browse(parent_id)
            if parent.exists():
                # Inherit down payment accounts from parent
                if 'property_account_down_payment_receivable_id' in fields_list and parent.property_account_down_payment_receivable_id:
                    defaults[
                        'property_account_down_payment_receivable_id'] = parent.property_account_down_payment_receivable_id.id

                if 'property_account_down_payment_payable_id' in fields_list and parent.property_account_down_payment_payable_id:
                    defaults[
                        'property_account_down_payment_payable_id'] = parent.property_account_down_payment_payable_id.id

        return defaults

    @api.onchange('parent_id')
    def _onchange_parent_id_down_payment_accounts(self):
        """Update down payment accounts when parent is changed"""
        if self.parent_id:
            if self.parent_id.property_account_down_payment_receivable_id:
                self.property_account_down_payment_receivable_id = self.parent_id.property_account_down_payment_receivable_id

            if self.parent_id.property_account_down_payment_payable_id:
                self.property_account_down_payment_payable_id = self.parent_id.property_account_down_payment_payable_id

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to ensure parent accounts are inherited"""
        for vals in vals_list:
            parent_id = vals.get('parent_id')
            if parent_id:
                parent = self.browse(parent_id)
                if parent.exists():
                    # Only inherit if not explicitly set
                    if 'property_account_down_payment_receivable_id' not in vals and parent.property_account_down_payment_receivable_id:
                        vals[
                            'property_account_down_payment_receivable_id'] = parent.property_account_down_payment_receivable_id.id

                    if 'property_account_down_payment_payable_id' not in vals and parent.property_account_down_payment_payable_id:
                        vals[
                            'property_account_down_payment_payable_id'] = parent.property_account_down_payment_payable_id.id

        return super(ResPartner, self).create(vals_list)
