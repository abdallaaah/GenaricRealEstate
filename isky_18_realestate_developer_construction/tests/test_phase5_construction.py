import ast
import os
import re
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

MODULE = 'isky_18_realestate_developer_construction'
L0 = 'isky_18_realestate_developer_unit_inventory'
L1 = 'isky_18_realestate_developer_accounting'
MONOLITH = 'arkzayed_18_realestate_development'

# Phase 5's first bullet: L4 depends on L0 and L1 only. Core and the Odoo modules L0 itself needs
# are not layers, so they are allowed alongside.
ALLOWED_DEPENDS = {'base', 'mail', 'project', L0, L1}

# The two monolith references Phase 5 deliberately left in place, both report-layer and both owned
# by Phase 3c (backlog #61). Listed here so the guard test below fails on a NEW one.
KNOWN_MONOLITH_REFS = {
    'wizard/report_wizard.py': ['%s.action_report_progress' % MONOLITH],
    'report/progress_report.py': ['report.%s.report_progress' % MONOLITH],
}


@tagged('post_install', '-at_install')
class TestPhase5Construction(TransactionCase):
    """Phase 5 acceptance: L4 installs standalone, depends on L0 (and optionally L1) only, and needs
    nothing from the cost distribution module. Two monolith group references that made this module's
    own gates dead are fixed here; see the decisions log, 2026-11-07."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project_type = cls.env['realestate.project.type'].create(
            {'project_type': 'residential'})
        cls.root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def setUp(self):
        super().setUp()
        self.project = self.env['realestate.project'].create({
            'name': 'C5 Project', 'abbreviation': 'C5P',
            'project_type_ids': [(6, 0, [self.project_type.id])]})
        self.unit = self.env['real.estate.unit'].create({
            'name': 'C5U01', 'abbreviation': 'C5U01',
            'parent_source_id': '%s,%d' % (self.project._name, self.project.id)})

        def _user(login, groups):
            return self.env['res.users'].create({
                'name': login, 'login': login, 'email': '%s@example.com' % login,
                'groups_id': [(6, 0, [self.env.ref('base.group_user').id] +
                               [self.env.ref(g).id for g in groups])]})

        self.engineer = _user('c5_engineer', ['%s.group_progress_engineer' % MODULE])
        self.other_engineer = _user('c5_other', ['%s.group_progress_engineer' % MODULE])
        self.manager = _user('c5_manager', ['%s.group_progress_manager' % MODULE])
        self.unit.responsible_engineer_id = self.engineer

    # -- the plan's two bullets ------------------------------------------------------------
    def test_depends_on_l0_and_l1_only(self):
        """Phase 5 bullet 1, read off the manifest rather than asserted from memory."""
        text = open(os.path.join(self.root, '__manifest__.py'), encoding='utf-8').read()
        # the file opens with a coding comment, which literal_eval cannot parse - evaluate from
        # the dict itself
        manifest = ast.literal_eval(text[text.index('{'):])
        depends = set(manifest['depends'])
        self.assertFalse(
            depends - ALLOWED_DEPENDS,
            "L4 may depend on L0, L1 and core only; found %s" % (depends - ALLOWED_DEPENDS))
        self.assertIn(L0, depends, "L4 is built on L0")

    def test_no_field_from_a_module_l4_does_not_require(self):
        """Decision 4: L4 must not name a field that only another layer's module declares. The
        vendor picker's old `supplier_rank` domain did exactly that - `supplier_rank` comes from
        Odoo's `account` module - and resolved against nothing on a standalone install."""
        field = self.env['vendor.commitment']._fields['vendor_id']
        self.assertFalse(
            field.domain,
            "vendor_id must carry no domain: the only one it had needed account's supplier_rank")
        # and the field is usable either way - this runs in all three Phase 5 gates, with and
        # without account present
        vendor = self.env['res.partner'].create({'name': 'C5 Domainless Vendor'})
        today = fields.Date.context_today(self.env['vendor.commitment'])
        self.assertTrue(self.env['vendor.commitment'].create({
            'vendor_id': vendor.id, 'commitment_type': 'permits', 'permit_name': 'C5 P2',
            'start_date': today, 'end_date': today + timedelta(days=60)}).id)

    def test_nothing_from_the_cost_distribution_module(self):
        """Phase 5 bullet 2, as a test rather than a one-off grep."""
        needles = ('arkzayed_cost_distribution', 'arkzayed.cost.allocation', 'cost.allocation')
        offenders = []
        for dirpath, _dirs, files in os.walk(self.root):
            if '__pycache__' in dirpath or os.sep + 'tests' in dirpath:
                continue
            for fn in files:
                if not fn.endswith(('.py', '.xml', '.csv')):
                    continue
                path = os.path.join(dirpath, fn)
                with open(path, encoding='utf-8') as fh:
                    for lineno, line in enumerate(fh, 1):
                        if any(n in line for n in needles):
                            offenders.append('%s:%d' % (os.path.relpath(path, self.root), lineno))
        self.assertFalse(offenders, "L4 must not reference cost distribution:\n%s"
                         % '\n'.join(offenders))

    # -- the two gates this phase repaired ------------------------------------------------
    def test_progress_manager_can_update_any_unit(self):
        """The group's whole purpose: a Progress Manager updates a unit they are not the
        responsible engineer of. Before Phase 5 this read the monolith's copy of the group, so
        has_group() was False for everyone and the manager was refused like anybody else."""
        self.assertTrue(self.manager.has_group('%s.group_progress_manager' % MODULE))
        update = self.env['arkzayed.construction.progress'].with_user(self.manager).create({
            'unit_id': self.unit.id, 'percent': 40.0, 'note': 'manager update'})
        self.assertTrue(update.id)
        self.assertEqual(update.user_id, self.manager)

    def test_responsible_engineer_can_update_their_own_unit(self):
        update = self.env['arkzayed.construction.progress'].with_user(self.engineer).create({
            'unit_id': self.unit.id, 'percent': 25.0})
        self.assertTrue(update.id)

    def test_unrelated_engineer_is_still_refused(self):
        """The fix widened nothing except the manager bypass."""
        with self.assertRaises(UserError):
            self.env['arkzayed.construction.progress'].with_user(self.other_engineer).create({
                'unit_id': self.unit.id, 'percent': 10.0})

    def test_vendor_commitment_cron_notifies_the_group(self):
        """The second repaired reference. The cron used to resolve the monolith's copy of
        `group_vendor_commitment_user`, get None, and return - so no expiry alert was ever sent."""
        watcher = self.env['res.users'].create({
            'name': 'c5_watcher', 'login': 'c5_watcher', 'email': 'c5_watcher@example.com',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('%s.group_vendor_commitment_user' % MODULE).id])]})
        # no supplier_rank: that field belongs to Odoo's `account` module, which L4 does not
        # require - setting it here is what first exposed the vendor_id domain (decision 4)
        vendor = self.env['res.partner'].create({'name': 'C5 Vendor'})
        today = fields.Date.context_today(self.env['vendor.commitment'])
        commitment = self.env['vendor.commitment'].create({
            'vendor_id': vendor.id, 'commitment_type': 'permits', 'permit_name': 'C5 Permit',
            'start_date': today - timedelta(days=30), 'end_date': today + timedelta(days=5)})

        before = len(commitment.message_ids)
        self.env['vendor.commitment']._cron_check_vendor_commitment_notifications()
        self.assertGreater(
            len(commitment.message_ids), before,
            "the cron must post an alert on a commitment expiring inside the 10-day window")
        self.assertIn(
            watcher.partner_id, commitment.message_ids[0].partner_ids,
            "the alert must reach a member of group_vendor_commitment_user")

    def test_group_reference_resolves_to_this_module(self):
        """Both groups are defined here (backlog #9 moved them), so the module's own xmlids must
        resolve - which is what makes the two gates above live at all."""
        for name in ('group_progress_manager', 'group_progress_engineer',
                     'group_vendor_commitment_user'):
            group = self.env.ref('%s.%s' % (MODULE, name))
            self.assertEqual(group._name, 'res.groups', name)

    # -- guard ----------------------------------------------------------------------------
    def test_no_new_monolith_reference(self):
        """L4 must not read groups, models or data from the monolith it does not depend on. The
        two report-layer references Phase 5 left for Phase 3c are allowlisted by file; anything
        else is the dead-gate bug class again (#45, #48, #59)."""
        pattern = re.compile(r"""['"]%s\.([A-Za-z0-9_.]+)['"]""" % MONOLITH)
        offenders = []
        for dirpath, _dirs, files in os.walk(self.root):
            if '__pycache__' in dirpath or os.sep + 'tests' in dirpath:
                continue
            for fn in files:
                if not fn.endswith(('.py', '.xml', '.csv')):
                    continue
                path = os.path.join(dirpath, fn)
                rel = os.path.relpath(path, self.root)
                allowed = KNOWN_MONOLITH_REFS.get(rel, [])
                with open(path, encoding='utf-8') as fh:
                    for lineno, line in enumerate(fh, 1):
                        for found in pattern.findall(line):
                            full = '%s.%s' % (MONOLITH, found)
                            if full in allowed or ('report.%s' % full) in allowed:
                                continue
                            offenders.append('%s:%d %s' % (rel, lineno, full))
        self.assertFalse(
            offenders,
            "L4 references the monolith outside the two allowlisted report-layer spots "
            "(backlog #61):\n%s" % '\n'.join(offenders))
