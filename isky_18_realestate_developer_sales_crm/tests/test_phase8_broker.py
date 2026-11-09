from odoo.tests.common import TransactionCase, tagged

L0 = 'isky_18_realestate_developer_unit_inventory'


@tagged('post_install', '-at_install')
class TestPhase8Broker(TransactionCase):
    """Phase 8 acceptance: "broker reads the code without recalculating it".

    The plan's two bullets are that the broker stores the system code as a char field with no
    computed logic, and that it reads the code from the developer product. These tests assert both
    halves, and the third thing that follows from them: once read, the stored code does not move
    on its own when the developer re-codes their hierarchy.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project_type = cls.env['realestate.project.type'].create(
            {'project_type': 'residential'})

    def setUp(self):
        super().setUp()
        self.project = self.env['realestate.project'].create({
            'name': 'P8 Project', 'abbreviation': 'P8P',
            'project_type_ids': [(6, 0, [self.project_type.id])]})
        self.dev_unit = self.env['real.estate.unit'].create({
            'name': 'P8U01', 'abbreviation': 'P8U01',
            'parent_source_id': '%s,%d' % (self.project._name, self.project.id)})
        self.assertTrue(self.dev_unit.system_code,
                        "the developer side must generate a code for this test to mean anything")
        self.seller = self.env['res.partner'].create(
            {'name': 'P8 Seller', 'is_resale_seller': True})

    def _broker_unit(self, **vals):
        vals.setdefault('name', 'P8 Broker Unit')
        vals.setdefault('unit_purpose', 'to_sale')
        vals.setdefault('unit_type', 'retail')
        # seller_client_id is required and NOT NULL on broker.unit - a resale unit always has a
        # selling owner. Nothing to do with Phase 8; just what the model demands.
        vals.setdefault('seller_client_id', self.seller.id)
        return self.env['broker.unit'].create(vals)

    # -- the acceptance --------------------------------------------------------------------
    def test_system_code_is_a_plain_stored_char(self):
        """No computed logic: not `compute`, not `related`, and stored like any other column."""
        field = self.env['broker.unit']._fields['system_code']
        self.assertEqual(field.type, 'char')
        self.assertFalse(field.compute, "the broker must not compute the code")
        self.assertFalse(field.related, "a related field is re-resolved on every read")
        self.assertTrue(field.store)

    def test_broker_reads_the_code_from_the_developer_unit(self):
        unit = self._broker_unit(developer_unit_id=self.dev_unit.id)
        self.assertEqual(unit.system_code, self.dev_unit.system_code)
        self.assertTrue(unit.system_code_matches_developer)

    def test_the_stored_code_does_not_follow_the_developer_afterwards(self):
        """The point of storing rather than computing: the stored code moves only when someone
        asks for it.

        Shown by repointing the link rather than by re-coding a unit - Phase 1 makes a unit's code
        immutable once its project holds a unit ("existing node codes never change"), which this
        test ran into and which is the developer side behaving correctly. Repointing is also the
        sharper check: a `related` field would have changed the instant the link changed.
        """
        unit = self._broker_unit(developer_unit_id=self.dev_unit.id)
        original = unit.system_code
        self.assertEqual(original, self.dev_unit.system_code)

        other = self.env['real.estate.unit'].create({
            'name': 'P8U02', 'abbreviation': 'P8U02',
            'parent_source_id': '%s,%d' % (self.project._name, self.project.id)})
        self.assertNotEqual(other.system_code, original)

        unit.write({'developer_unit_id': other.id})
        self.assertEqual(unit.system_code, original,
                         "writing the link must not recalculate the stored code")
        self.assertFalse(unit.system_code_matches_developer,
                         "but the mismatch must be visible")

        unit.action_refresh_system_code()
        self.assertEqual(unit.system_code, other.system_code,
                         "re-reading is an explicit act, and it works")
        self.assertTrue(unit.system_code_matches_developer)

    def test_picking_a_developer_unit_on_the_form_fills_the_code(self):
        """The user-facing half of the same rule: the onchange offers the code when someone picks
        a developer unit in the form, so nobody has to retype it."""
        unit = self._broker_unit()
        self.assertFalse(unit.system_code)
        form_unit = unit.with_context(test_onchange=True)
        form_unit.developer_unit_id = self.dev_unit
        form_unit._onchange_developer_unit_id()
        self.assertEqual(form_unit.system_code, self.dev_unit.system_code)

    def test_a_broker_can_hold_a_code_with_no_developer_record_at_all(self):
        """The broker branch may run on a database with no developer units: the developer hands
        over a code and the broker stores it."""
        unit = self._broker_unit(system_code='EXT-BLOCK-7-0412')
        self.assertFalse(unit.developer_unit_id)
        self.assertEqual(unit.system_code, 'EXT-BLOCK-7-0412')
        self.assertFalse(unit.system_code_matches_developer,
                         "nothing to compare against, so the flag is False rather than True")

    def test_a_code_given_at_creation_wins_over_the_link(self):
        """If the broker was handed a code, creating the record does not overwrite it with the
        developer's - the two can legitimately differ while a re-code is in flight."""
        unit = self._broker_unit(
            developer_unit_id=self.dev_unit.id, system_code='AS-HANDED-OVER')
        self.assertEqual(unit.system_code, 'AS-HANDED-OVER')
        self.assertFalse(unit.system_code_matches_developer)

    def test_unlinking_the_developer_unit_keeps_the_code(self):
        unit = self._broker_unit(developer_unit_id=self.dev_unit.id)
        code = unit.system_code
        unit.developer_unit_id = False
        self.assertEqual(unit.system_code, code,
                         "the broker was given this code; losing the link does not unsay it")

    # -- G4, the owner's decision of 2026-11-08 -------------------------------------------
    def test_company_type_defaults_to_developer(self):
        company = self.env['res.company'].create({'name': 'P8 Co'})
        self.assertEqual(company.realestate_company_type, 'developer',
                         "every existing database must keep behaving as a developer")
        self.assertFalse(company._is_broker())

    def test_company_type_offers_exactly_developer_and_broker(self):
        field = self.env['res.company']._fields['realestate_company_type']
        self.assertEqual([code for code, _label in field.selection],
                         ['developer', 'broker'])

    def test_company_type_is_switchable_and_readable(self):
        company = self.env.company
        company.realestate_company_type = 'broker'
        self.assertTrue(company._is_broker())
        company.realestate_company_type = 'developer'
        self.assertFalse(company._is_broker())

    def test_company_type_is_not_named_company_type(self):
        """D2: `res.partner` already has a `company_type` (person / company). Two fields of that
        name on two models this closely related is a trap, so ours carries the prefix."""
        self.assertIn('realestate_company_type', self.env['res.company']._fields)
        partner_field = self.env['res.partner']._fields.get('company_type')
        self.assertTrue(partner_field, "res.partner.company_type is the field we avoided clashing with")
        self.assertNotEqual(
            self.env['res.company']._fields['realestate_company_type'].selection,
            partner_field.selection)

    def test_company_type_sits_in_company_setup(self):
        """It is the first setting that section has ever held."""
        from lxml import etree
        arch = etree.fromstring(self.env['res.config.settings'].get_view()['arch'])
        container = arch.xpath("//div[@id='realestate_company_setup_section']")
        self.assertEqual(len(container), 1)
        names = [f.get('name') for f in container[0].xpath('.//field[@name]')]
        self.assertIn('realestate_company_type', names)
