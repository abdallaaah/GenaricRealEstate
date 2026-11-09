from odoo.tests.common import TransactionCase, tagged

from ..models.config.company_type import COMPANY_TYPES


@tagged('post_install', '-at_install')
class TestPhase8CompanyType(TransactionCase):
    """Phase 8 / G4 on the minimal configuration: the company type lives in L0, so a database
    with no sales, commission or accounting module still has it and still defaults to developer."""

    def test_the_two_types_and_the_default(self):
        self.assertEqual([code for code, _label in COMPANY_TYPES], ['developer', 'broker'])
        company = self.env['res.company'].create({'name': 'P8 L0 Co'})
        self.assertEqual(company.realestate_company_type, 'developer')

    def test_it_is_required_so_no_company_is_undecided(self):
        field = self.env['res.company']._fields['realestate_company_type']
        self.assertTrue(field.required)

    def test_the_broker_helper_answers_for_both_types(self):
        company = self.env['res.company'].create(
            {'name': 'P8 L0 Broker', 'realestate_company_type': 'broker'})
        self.assertTrue(company._is_broker())
        company.realestate_company_type = 'developer'
        self.assertFalse(company._is_broker())
