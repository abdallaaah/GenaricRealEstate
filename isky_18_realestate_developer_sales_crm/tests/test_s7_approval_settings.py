import os
import re

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

from ..models.config.approval_settings import APPROVAL_STAGES, NON_CONFIGURABLE_GATES

SC = 'isky_18_realestate_developer_sales_crm'


@tagged('post_install', '-at_install')
class TestS7ApprovalSettings(TransactionCase):
    """S7 acceptance: configurable approver groups, one on/off switch, gates stay in code."""

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.partner = self.env['res.partner'].create({
            'name': 'S7 Customer', 'national_id': 'S7-NID-0001'})

    def _user(self, login, groups=()):
        return self.env['res.users'].create({
            'name': login, 'login': login, 'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id] + [g.id for g in groups])]})

    def _contract(self):
        return self.env['sale.proposal'].create({
            'customer_id': self.partner.id, 'company_id': self.company.id})

    # -- 1 ---------------------------------------------------------------------------------
    def test_default_groups_match_current_behaviour(self):
        """With defaults, every stage points at exactly the group its gate used to hardcode."""
        expected = {
            'finance': 'group_finance_approval',
            'finance_two': 'group_finance_two_approval',
            'manager': 'group_manager_approval',
            'confirm_reservation': 'group_confirm_reservation',
            'show_discount': 'group_show_discount_percentage',
            'edit_discount': 'group_edit_discount_percentage',
            'manual_paid': 'group_manual_paid_installment',
        }
        for stage, xmlid in expected.items():
            group = self.env.ref('%s.%s' % (SC, xmlid))
            configured = self.company._approver_groups(stage)
            self.assertEqual(
                configured, group,
                "stage '%s' must default to %s, got %s" % (stage, xmlid, configured.mapped('name')))

        # a member of the default group passes; a plain user does not
        for stage, xmlid in expected.items():
            member = self._user('s7_m_%s' % stage, [self.env.ref('%s.%s' % (SC, xmlid))])
            plain = self._user('s7_p_%s' % stage)
            rec = self._contract()
            self.assertTrue(rec.with_user(member)._user_can_approve(stage), stage)
            self.assertFalse(rec.with_user(plain)._user_can_approve(stage), stage)

    # -- 2 ---------------------------------------------------------------------------------
    def test_group_change_applies_to_pending_record(self):
        """Decision 1: groups are read at the moment of the action, not snapshotted."""
        old_group = self.env.ref('%s.group_manager_approval' % SC)
        new_group = self.env['res.groups'].create({'name': 'S7 New Managers'})
        old_member = self._user('s7_old_mgr', [old_group])
        new_member = self._user('s7_new_mgr', [new_group])

        contract = self._contract()          # created while the OLD group is configured
        self.assertTrue(contract.with_user(old_member)._user_can_approve('manager'))

        self.company.manager_approver_group_ids = [(6, 0, new_group.ids)]

        self.assertTrue(
            contract.with_user(new_member)._user_can_approve('manager'),
            "a member of the newly configured group must be able to approve a pending record")
        self.assertFalse(
            contract.with_user(old_member)._user_can_approve('manager'),
            "a member of only the old group must now be refused")

    # -- 3 ---------------------------------------------------------------------------------
    def test_approval_off_skips_approval_stages_only(self):
        """The switch skips approval stages; unit blocking and the reservation exception are
        always enforced (decision 4)."""
        plain = self._user('s7_off_plain')
        contract = self._contract()

        self.company.approval_enabled = False
        for stage, spec in APPROVAL_STAGES.items():
            if not spec['has_python_gate']:
                continue
            self.assertTrue(
                contract.with_user(plain)._user_can_approve(stage),
                "stage '%s' must be skipped when approvals are off" % stage)

        # the two non-configurable gates still refuse a non-member
        self.assertFalse(
            plain.has_group(NON_CONFIGURABLE_GATES['block_unit']),
            "the plain user must not be in the unit-blocking group")
        self.assertFalse(
            plain.has_group(NON_CONFIGURABLE_GATES['exception_reservation']),
            "the plain user must not be in the exception-reservation group")

        reservation = self.env['real.estate.sale.reservation'].create({
            'customer_id': self.partner.id, 'company_id': self.company.id})
        with self.assertRaises(UserError, msg="exception reservation must stay enforced"):
            reservation.with_user(plain).action_exception_reservation()

        # sale.request's gate is _check_approval_rights(), which raises ValidationError on
        # unit_inventory.group_block_unit - never routed through _user_can_approve(), so the
        # switch cannot reach it. Called directly, since building a full sale.request needs a
        # unit and a block reason and the gate is what is under test.
        with self.assertRaises(ValidationError, msg="unit blocking must stay enforced"):
            self.env['sale.request'].with_user(plain)._check_approval_rights()

    # -- 4 ---------------------------------------------------------------------------------
    def test_empty_group_refused_when_approval_on(self):
        """An approval stage with no group, while approvals are on, cannot be saved."""
        self.company.approval_enabled = True
        with self.assertRaises(ValidationError) as caught:
            self.company.manager_approver_group_ids = [(5, 0, 0)]
        self.assertIn('Manager Approval', str(caught.exception))

        # and it IS allowed once approvals are off
        self.company.approval_enabled = False
        self.company.manager_approver_group_ids = [(5, 0, 0)]
        self.assertFalse(self.company.manager_approver_group_ids)

    def test_empty_group_at_action_time_refuses_loudly(self):
        """A stage with no configured group refuses the action and names the stage - it is never
        silently allowed.

        Uses the `operation_manager` stage, which ships with no default on purpose: the group the
        S7 spec named for it lives in the monolith and this module cannot see it. That makes it
        the one stage that is legitimately empty while approvals are on, so no contrivance is
        needed to reach this branch - and it is exactly the state a half-configured system is in.
        """
        self.company.approval_enabled = True
        self.assertFalse(self.company.operation_manager_approver_group_ids,
                         "operation_manager ships with no default group")
        contract = self._contract()
        with self.assertRaises(UserError) as caught:
            contract._user_can_approve('operation_manager')
        message = str(caught.exception)
        self.assertIn('Sales Sector Manager Approval', message, "the stage must be named")
        self.assertIn('no approver group', message.lower())
        self.assertIn(self.company.name, message)

    # -- 5 ---------------------------------------------------------------------------------
    def test_group_change_writes_audit_row(self):
        """Decision 3: who changed it, when, old value, new value."""
        Audit = self.env['realestate.approval.audit']
        new_group = self.env['res.groups'].create({'name': 'S7 Audit Target'})
        before_ids = self.company.manager_approver_group_ids.ids
        count = Audit.search_count([])

        self.company.manager_approver_group_ids = [(6, 0, new_group.ids)]

        rows = Audit.search([('entry_type', '=', 'config'),
                             ('field_name', '=', 'manager_approver_group_ids')],
                            order='id desc', limit=1)
        self.assertEqual(Audit.search_count([]), count + 1, "exactly one audit row")
        self.assertEqual(rows.stage, 'manager')
        self.assertEqual(rows.company_id, self.company)
        self.assertEqual(rows.old_value, str(before_ids))
        self.assertEqual(rows.new_value, str(new_group.ids))
        self.assertEqual(rows.create_uid, self.env.user, "the audit row records who changed it")
        self.assertTrue(rows.create_date, "and when")

    def test_switch_change_writes_audit_row(self):
        Audit = self.env['realestate.approval.audit']
        count = Audit.search_count([])
        self.company.approval_enabled = False
        rows = Audit.search([('field_name', '=', 'approval_enabled')], order='id desc', limit=1)
        self.assertEqual(Audit.search_count([]), count + 1)
        self.assertEqual((rows.old_value, rows.new_value), ('True', 'False'))

    # -- 6 ---------------------------------------------------------------------------------
    def test_approval_records_store_approver_and_matched_group(self):
        """Decision 3: each approval stores the approver, the timestamp, and the group matched."""
        group = self.env.ref('%s.group_manager_approval' % SC)
        member = self._user('s7_approver', [group])
        contract = self._contract()

        Audit = self.env['realestate.approval.audit']
        count = Audit.search_count([('entry_type', '=', 'approval')])
        contract.with_user(member).write({'manager_approve': True})

        rows = Audit.search([('entry_type', '=', 'approval')], order='id desc', limit=1)
        self.assertEqual(Audit.search_count([('entry_type', '=', 'approval')]), count + 1)
        self.assertEqual(rows.approver_id, member, "the approver is recorded")
        self.assertEqual(rows.matched_group_id, group, "and the group they matched on")
        self.assertEqual(rows.stage, 'manager')
        self.assertEqual((rows.res_model, rows.res_id), ('sale.proposal', contract.id))
        self.assertTrue(rows.create_date, "and the timestamp")

    def test_non_member_cannot_approve_through_write(self):
        plain = self._user('s7_write_plain')
        contract = self._contract()
        with self.assertRaises(UserError):
            contract.with_user(plain).write({'manager_approve': True})

    # -- 7 ---------------------------------------------------------------------------------
    def test_no_hardcoded_group_check_left(self):
        """No approval stage may call has_group() on a hardcoded xmlid. The two
        non-configurable gates are the only permitted exceptions (decision 4)."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        allowed = set(NON_CONFIGURABLE_GATES.values())
        pattern = re.compile(r"""has_group\(\s*['"]([a-zA-Z0-9_.]+)['"]""")
        offenders = []
        for dp, _dirs, files in os.walk(root):
            if '__pycache__' in dp or os.sep + 'tests' in dp:
                continue
            for fn in files:
                if not fn.endswith('.py'):
                    continue
                path = os.path.join(dp, fn)
                for lineno, line in enumerate(open(path, encoding='utf-8'), 1):
                    for xmlid in pattern.findall(line):
                        stage_group = any(
                            spec['default'] and spec['default'] == xmlid
                            for spec in APPROVAL_STAGES.values())
                        if stage_group and xmlid not in allowed:
                            offenders.append('%s:%d %s' % (
                                os.path.relpath(path, root), lineno, xmlid))
        self.assertFalse(
            offenders,
            "configurable approval stages must go through _user_can_approve(); found:\n%s"
            % '\n'.join(offenders))

    def test_stage_registry_matches_settings_fields(self):
        """Every stage in the registry has its company field and its settings field."""
        for stage, spec in APPROVAL_STAGES.items():
            self.assertIn(spec['field'], self.env['res.company']._fields,
                          "stage '%s' has no company field" % stage)
            self.assertIn(spec['field'], self.env['res.config.settings']._fields,
                          "stage '%s' is not surfaced in settings" % stage)
