from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountAnalyticAccount(models.Model):
    _inherit = "account.analytic.account"

    is_gis_account = fields.Boolean(string="Is GIS Account")
    is_oaya_account = fields.Boolean(string="Is OAYA Account")

    @api.constrains('is_gis_account', 'is_oaya_account')
    def _check_unique_account_flags(self):
        for record in self:
            # Check for unique GIS Account
            if record.is_gis_account:
                # Search for any OTHER record that already has this flag
                domain = [('is_gis_account', '=', True), ('id', '!=', record.id)]
                if self.search_count(domain) > 0:
                    raise ValidationError(_("Only one record can be marked as a GIS Account."))

            # Check for unique OAYA Account
            if record.is_oaya_account:
                # Search for any OTHER record that already has this flag
                domain = [('is_oaya_account', '=', True), ('id', '!=', record.id)]
                if self.search_count(domain) > 0:
                    raise ValidationError(_("Only one record can be marked as an OAYA Account."))

