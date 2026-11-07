from lxml import etree

from odoo.tests.common import TransactionCase, tagged

L0 = 'isky_18_realestate_developer_unit_inventory'
SECTION_NAMES = ['Company Setup', 'Sales Setup', 'Commission', 'Financials', 'Units']


@tagged('post_install', '-at_install')
class TestPhase6UnitsSection(TransactionCase):
    """Phase 6: L0 declares the shared settings tab, so the minimal configuration - L0 with no
    sales, commission or accounting module - must still install it and show the Units section.
    The cross-module uniqueness check lives in sales_crm's suite, which runs where more than one
    module contributes settings."""

    def test_l0_declares_the_tab_and_the_five_sections(self):
        arch = etree.fromstring(
            self.env.ref('%s.res_config_settings_view_form_real_estate' % L0).arch)
        self.assertTrue(arch.xpath("//div[@data-key='realestate_settings']"))
        self.assertEqual([(h.text or '').strip() for h in arch.xpath('//h2')], SECTION_NAMES)

    def test_units_section_holds_the_hierarchy_template(self):
        settings = self.env['res.config.settings']
        self.assertIn('hierarchy_template_id', settings._fields)
        arch = etree.fromstring(settings.get_view()['arch'])
        container = arch.xpath("//div[@id='realestate_units_section']")
        self.assertEqual(len(container), 1)
        self.assertEqual(
            [f.get('name') for f in container[0].xpath('.//field[@name]')],
            ['hierarchy_template_id'])

    def test_the_setting_writes_through_to_the_company(self):
        """related= + readonly=False, so saving the form writes the company field. No default or
        value changed in Phase 6 - this only proves the plumbing."""
        template = self.env['realestate.hierarchy.template'].search([], limit=1)
        if not template:
            self.skipTest('no hierarchy template in this database')
        self.env['res.config.settings'].create(
            {'hierarchy_template_id': template.id}).execute()
        self.assertEqual(self.env.company.hierarchy_template_id, template)
