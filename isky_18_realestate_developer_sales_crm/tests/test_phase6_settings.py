from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

ISKY_PREFIX = 'isky_18_realestate_developer_'
L0 = ISKY_PREFIX + 'unit_inventory'
TAB_KEY = 'realestate_settings'

# The five sections the plan allows, in the order L0 declares them, with the container each one
# wraps. Nothing else may appear as a section of this tab.
SECTIONS = [
    ('Company Setup', 'realestate_company_setup_section'),
    ('Sales Setup', 'realestate_sales_setup_section'),
    ('Commission', 'realestate_commission_section'),
    ('Financials', 'realestate_financials_section'),
    ('Units', 'realestate_units_section'),
]


@tagged('post_install', '-at_install')
class TestPhase6Settings(TransactionCase):
    """Phase 6 acceptance: "every setting is in its section, with no duplicates".

    Read from the **installed** settings form, not from source files and not from a hand-kept
    list: the arch is fetched through `get_view`, so every inheriting view of every installed
    module has already been applied. That is what a user actually sees.

    Deliberately scoped to the sections of the shared "Real Estate" tab, which the
    `isky_*` modules own. `arkzayed_18_realestate_development` still renders 17 of these same
    settings in a legacy tab of its own until Phase 3c retires that view (backlog #65); that is a
    duplicate rendering outside this product's settings, and removing it would be a legacy edit,
    which Phase 6 was not authorised to make.
    """

    def setUp(self):
        super().setUp()
        # a real administrator, not the superuser: opening the settings form requires
        # base.group_system, and that is the access this test exercises
        self.settings_admin = self.env['res.users'].create({
            'name': 'p6_admin', 'login': 'p6_admin', 'email': 'p6_admin@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('base.group_system').id])]})
        self.plain_user = self.env['res.users'].create({
            'name': 'p6_plain', 'login': 'p6_plain', 'email': 'p6_plain@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]})

    def _tab(self, user=None):
        """The fully-inherited arch of our settings tab, as the given user sees it."""
        settings = self.env['res.config.settings']
        if user is not None:
            settings = settings.with_user(user)
        arch = etree.fromstring(settings.get_view()['arch'])
        tabs = arch.xpath("//div[@data-key='%s']" % TAB_KEY)
        self.assertEqual(len(tabs), 1,
                         "exactly one Real Estate settings tab must exist, found %d" % len(tabs))
        return tabs[0]

    def _declared_isky_settings(self):
        """Every res.config.settings field an installed isky module declares."""
        rows = self.env['ir.model.fields'].search([('model', '=', 'res.config.settings')])
        names = set()
        for row in rows:
            modules = [m.strip() for m in (row.modules or '').split(',')]
            if any(m.startswith(ISKY_PREFIX) for m in modules):
                names.add(row.name)
        self.assertTrue(names, "the isky modules must declare some settings")
        return names

    def _fields_by_section(self, tab):
        """section name -> list of field names rendered in it (duplicates kept, so they show up)."""
        found = {}
        for name, container_id in SECTIONS:
            containers = tab.xpath(".//div[@id='%s']" % container_id)
            self.assertEqual(
                len(containers), 1,
                "section '%s' must have exactly one container, found %d" % (name, len(containers)))
            # Only settings fields count. A field with an inline list - Phase 7's revenue split
            # rows, for instance - renders ITS model's fields underneath, and those belong to
            # that model, not to res.config.settings.
            found[name] = [
                f.get('name') for f in containers[0].xpath('.//field[@name]')
                if not f.xpath('ancestor::field')]
        return found

    # -- the acceptance criterion ---------------------------------------------------------
    def test_every_setting_is_in_exactly_one_section(self):
        tab = self._tab(self.settings_admin)
        by_section = self._fields_by_section(tab)

        placements = {}
        for section, names in by_section.items():
            for name in names:
                placements.setdefault(name, []).append(section)

        twice = {n: s for n, s in placements.items() if len(s) > 1}
        self.assertFalse(twice, "these settings appear more than once: %s" % twice)

        declared = self._declared_isky_settings()
        homeless = sorted(declared - set(placements))
        self.assertFalse(
            homeless,
            "every setting an isky module declares must have a section; these have none: %s"
            % homeless)

        # and nothing is rendered here that no isky module declares - which would mean a field
        # drifted in from elsewhere, or a typo that silently renders nothing
        stray = sorted(set(placements) - declared)
        self.assertFalse(stray, "rendered in our sections but declared by no isky module: %s"
                         % stray)

    def test_only_the_five_section_names_are_used(self):
        tab = self._tab(self.settings_admin)
        headings = [(h.text or '').strip() for h in tab.xpath('.//h2')]
        self.assertEqual(
            headings, [name for name, _id in SECTIONS],
            "the tab must show exactly the plan's five sections, in order")
        # a second check with a different failure mode: no heading anywhere in the tab outside
        # the five, whatever its level
        for tag in ('h1', 'h3', 'h4'):
            self.assertFalse(
                tab.xpath('.//%s' % tag),
                "sections are <h2> only; found a <%s> in the Real Estate tab" % tag)

    def test_l0_owns_the_tab_and_the_five_headings(self):
        """The structural rule behind the two tests above (decisions log, P1 + P2 amendment):
        only L0 may declare the tab or a section heading, because Financials and Sales Setup each
        hold settings from two modules that must not depend on each other."""
        root = self.env.ref('%s.res_config_settings_view_form_real_estate' % L0)
        arch = etree.fromstring(root.arch)
        self.assertTrue(arch.xpath("//div[@data-key='%s']" % TAB_KEY))
        self.assertEqual(
            [(h.text or '').strip() for h in arch.xpath('//h2')],
            [name for name, _id in SECTIONS])

        inheriting = self.env['ir.ui.view'].search([
            ('model', '=', 'res.config.settings'), ('inherit_id', '=', root.id)])
        for view in inheriting:
            view_arch = etree.fromstring(view.arch)
            self.assertFalse(
                view_arch.xpath('//h2'),
                "%s declares a section heading; only L0 may (it would duplicate a section when "
                "two modules contribute to one)" % view.xml_id)
            self.assertFalse(
                view_arch.xpath("//div[contains(@class, 'app_settings_block')]"),
                "%s declares a settings tab of its own; there is one Real Estate tab"
                % view.xml_id)

    # -- access ---------------------------------------------------------------------------
    def test_settings_need_the_administrator_group(self):
        """Phase 6 changed no permission: reading the settings still needs base.group_system."""
        self.assertTrue(self.settings_admin.has_group('base.group_system'))
        self.assertFalse(self.plain_user.has_group('base.group_system'))
        # the admin can open the form
        self.assertTrue(self._tab(self.settings_admin) is not None)
        with self.assertRaises(AccessError):
            self.env['res.config.settings'].with_user(self.plain_user).create({})

    def test_approval_settings_are_three_entries_in_sales_setup(self):
        """S7's constraint survives the move: one switch plus two approver blocks, all inside
        Sales Setup, and the two non-configurable gates are still absent."""
        by_section = self._fields_by_section(self._tab(self.settings_admin))
        sales = set(by_section['Sales Setup'])
        self.assertIn('approval_enabled', sales)
        for group_field in ('finance_approver_group_ids', 'finance_two_approver_group_ids',
                            'manager_approver_group_ids',
                            'operation_manager_approver_group_ids',
                            'confirm_reservation_group_ids', 'show_discount_group_ids',
                            'edit_discount_group_ids', 'manual_paid_group_ids'):
            self.assertIn(group_field, sales, group_field)
        for never_configurable in ('group_block_unit', 'block_unit_group_ids',
                                   'reservation_exception_group_ids'):
            self.assertNotIn(
                never_configurable, sales,
                "unit blocking and the reservation exception are not configurable "
                "(decisions log section 11, decision 2)")
