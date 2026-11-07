from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPhase7TaxRates(TransactionCase):
    """Phase 7 (D4): the VAT divisor and the withholding rate were the literals 1.14 and 0.05
    inside `broker_claim`. They are company configuration now, and the defaults reproduce the old
    arithmetic exactly - which is what these tests pin."""

    def setUp(self):
        super().setUp()
        self.company = self.env.company

    def _claim(self, unit_price, commission_percent, with_withholding=True):
        """An in-memory claim, on purpose: the subject here is the tax arithmetic, and a stored
        claim additionally requires a unit under contract with the broker - a product rule of its
        own that has nothing to do with Phase 7. Computes run on `new()` records."""
        return self.env['broker.claim'].new({
            'company_id': self.company.id,
            'unit_sold_price': unit_price,
            'commission': commission_percent,
            'with_withholding_tax': with_withholding,
        })

    def test_defaults_are_the_old_constants(self):
        self.assertEqual(self.company.vat_rate, 14.0)
        self.assertEqual(self.company.withholding_tax_rate, 5.0)
        self.assertAlmostEqual(self.company._vat_divisor(), 1.14, places=10)

    def test_amounts_match_the_old_literals(self):
        claim = self._claim(1_000_000.0, 2.0)
        gross = 1_000_000.0 * 2.0 / 100
        expected_net_of_vat = gross / 1.14
        expected_withholding = expected_net_of_vat * 0.05
        # places=2: these are Monetary fields, so the stored value is rounded to the currency's
        # precision - as it was before Phase 7. The point is the arithmetic, not the rounding.
        self.assertAlmostEqual(claim.commission_amount_with_vat, gross, places=2)
        self.assertAlmostEqual(claim.commission_amount_without_vat, expected_net_of_vat, places=2)
        self.assertAlmostEqual(claim.withholding_tax, expected_withholding, places=2)
        self.assertAlmostEqual(claim.paid_commission, gross - expected_withholding, places=2)

    def test_changing_the_rates_changes_the_claim(self):
        """The point of the phase: these are configuration, so a company with different rates
        gets different numbers without a code change."""
        self.company.write({'vat_rate': 0.0, 'withholding_tax_rate': 10.0})
        claim = self._claim(1_000_000.0, 2.0)
        gross = 20_000.0
        self.assertAlmostEqual(claim.commission_amount_without_vat, gross, places=2,
                               msg="with 0% VAT the net-of-VAT amount is the gross")
        self.assertAlmostEqual(claim.withholding_tax, gross * 0.10, places=2)

    def test_withholding_can_be_switched_off_per_claim(self):
        claim = self._claim(1_000_000.0, 2.0, with_withholding=False)
        self.assertAlmostEqual(claim.paid_commission, claim.commission_amount_with_vat, places=2)

    def test_impossible_rates_are_refused(self):
        with self.assertRaises(ValidationError):
            self.company.vat_rate = -100.0
        with self.assertRaises(ValidationError):
            self.company.withholding_tax_rate = -1.0
