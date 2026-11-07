from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    """Phase 7 (D4): the VAT divisor and the withholding rate used to be the literals 1.14 and
    0.05 inside `broker_claim._compute_commission_amounts`. They are company configuration, and
    they live in the Financials section.

    The defaults reproduce the old constants exactly - 14% VAT gives the 1.14 divisor, 5%
    withholding gives the 0.05 multiplier - so no existing claim changes value.
    """
    _inherit = 'res.company'

    vat_rate = fields.Float(
        string='VAT Rate (%)', default=14.0,
        help="VAT included in a broker commission. The commission excluding VAT is the gross "
             "divided by (1 + this rate / 100).")
    withholding_tax_rate = fields.Float(
        string='Withholding Tax Rate (%)', default=5.0,
        help="Withholding tax taken on the commission excluding VAT.")

    @api.constrains('vat_rate', 'withholding_tax_rate')
    def _check_tax_rates(self):
        for company in self:
            if company.vat_rate <= -100.0:
                raise ValidationError(_(
                    "VAT Rate cannot be -100% or lower: it would make the net-of-VAT divisor "
                    "zero or negative."))
            for value, label in ((company.vat_rate, _("VAT Rate")),
                                 (company.withholding_tax_rate, _("Withholding Tax Rate"))):
                if value < 0.0:
                    raise ValidationError(_("%s cannot be negative.", label))

    def _vat_divisor(self):
        """What a gross, VAT-inclusive amount is divided by to get the amount excluding VAT."""
        self.ensure_one()
        return 1.0 + (self.vat_rate or 0.0) / 100.0
