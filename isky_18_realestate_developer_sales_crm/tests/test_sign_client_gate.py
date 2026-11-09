import ast
import os

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

from ..models.config.approval_settings import APPROVAL_STAGES
from ..models.core.sale_proposal import SIGNING_STATES

SC = 'isky_18_realestate_developer_sales_crm'


@tagged('post_install', '-at_install')
class TestSignClientGate(TransactionCase):
    """The `sign_client` gate: no ordinary salesperson may move a sale into a signing state.

    Every test acts as a real user through `with_user(...)`. Odoo tests otherwise run as
    superuser, which bypasses both ACLs and - because `_user_can_approve()` reads
    `self.env.user` - the approval gate itself, so a test written without `with_user` would
    pass whatever the gate said. That is the lesson 12.2 recorded, applied here.

    The audit that prompted this gate is `claude/signed_by_client_state.md`: it measured a
    salesperson writing `state = 'signed_client'` and the commission record appearing.
    """

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.partner = self.env['res.partner'].create({
            'name': 'SC Gate Customer', 'national_id': 'SCG-NID-0001'})
        self.team_lead_group = self.env.ref('%s.sales_team_lead_group' % SC)
        self.manager_group = self.env.ref('%s.sales_manager_group' % SC)
        self.salesman_group = self.env.ref('sales_team.group_sale_salesman')
        self.Audit = self.env['realestate.approval.audit']

        # The three actors. All internal, all holding the base sales rights that let them reach
        # a contract at all: sale.proposal grants base.group_user 1,1,1,0 (12.2), so write
        # access is not what separates them - only the approval stage is.
        self.salesperson = self._user('scg_sales', [self.salesman_group])
        self.team_lead = self._user('scg_lead', [self.team_lead_group])
        self.manager = self._user('scg_manager', [self.manager_group])

    def _user(self, login, groups=()):
        return self.env['res.users'].create({
            'name': login, 'login': login, 'email': '%s@example.com' % login,
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id] + [g.id for g in groups])]})

    def _contract(self):
        """A contract in `draft`, with no unit and no installments.

        Deliberately bare: writing `signed_client` on a contract that has a unit also marks the
        unit sold, and a contract with collected installments would start a commission. Neither
        belongs in a test about who may sign.
        """
        return self.env['sale.proposal'].create({
            'customer_id': self.partner.id, 'company_id': self.company.id})

    # -- the group and the stage are wired as decided (SC-D1, SC-D2) -----------------------
    def test_group_sits_between_salesperson_and_manager(self):
        """A strict superset of Salesperson, and a subset of Sales Manager."""
        self.assertIn(self.salesman_group, self.team_lead_group.implied_ids,
                      "Sales Team Lead must imply the salesperson group")
        self.assertIn(self.team_lead_group, self.manager_group.implied_ids,
                      "Sales Manager must imply Sales Team Lead, so a manager can sign")

        # and the membership that follows from it, as the users actually resolve it
        self.assertTrue(self.team_lead.has_group('sales_team.group_sale_salesman'))
        self.assertTrue(self.manager.has_group('%s.sales_team_lead_group' % SC),
                        "a manager holds the team-lead group through the implied chain")
        self.assertFalse(self.salesperson.has_group('%s.sales_team_lead_group' % SC),
                         "an ordinary salesperson must NOT hold it")

    def test_stage_defaults_to_the_team_lead_group(self):
        self.assertEqual(APPROVAL_STAGES['sign_client']['label'], 'Sign by Client')
        self.assertTrue(APPROVAL_STAGES['sign_client']['has_python_gate'],
                        "the stage must be python-gated, so the 'no group configured' "
                        "constrains covers it")
        self.assertEqual(self.company._approver_groups('sign_client'), self.team_lead_group,
                         "the stage must be seeded with the team-lead group on a fresh database")

    # -- the refusals ----------------------------------------------------------------------
    def test_salesperson_cannot_set_signed_client(self):
        contract = self._contract()
        with self.assertRaises(UserError) as caught:
            contract.with_user(self.salesperson).write({'state': 'signed_client'})
        self.assertIn('Sign by Client', str(caught.exception),
                      "the refusal must name the stage, so the user knows what they lack")
        contract.invalidate_recordset(['state'])
        self.assertEqual(contract.state, 'draft', "the state must not have moved")

    def test_salesperson_cannot_set_signed_by_client(self):
        contract = self._contract()
        with self.assertRaises(UserError):
            contract.with_user(self.salesperson).write({'signed_by_client': True})
        contract.invalidate_recordset(['signed_by_client'])
        self.assertFalse(contract.signed_by_client)

    def test_salesperson_cannot_set_signed_ceo_either(self):
        """SC-D4: both signing states are gated, not only the first one.

        Without this the gate would be trivially bypassable - the audit measured a salesperson
        reaching `signed_ceo` directly from `draft`, and `signed_ceo` is commission-eligible
        for exactly the same reason `signed_client` is.
        """
        contract = self._contract()
        with self.assertRaises(UserError):
            contract.with_user(self.salesperson).write({'state': 'signed_ceo'})
        contract.invalidate_recordset(['state'])
        self.assertEqual(contract.state, 'draft')

    # -- the permissions -------------------------------------------------------------------
    def test_team_lead_can_sign(self):
        contract = self._contract()
        before = self.Audit.search_count([])
        contract.with_user(self.team_lead).write({'state': 'signed_client'})
        contract.invalidate_recordset(['state'])
        self.assertEqual(contract.state, 'signed_client')

        rows = self.Audit.search([
            ('entry_type', '=', 'approval'), ('stage', '=', 'sign_client'),
            ('res_model', '=', 'sale.proposal'), ('res_id', '=', contract.id)])
        self.assertEqual(len(rows), 1, "exactly one audit row for the signature")
        self.assertEqual(rows.approver_id, self.team_lead, "recording who signed")
        self.assertEqual(rows.matched_group_id, self.team_lead_group,
                         "and the group they matched on")
        self.assertEqual(rows.company_id, self.company)
        self.assertTrue(rows.create_date, "and when")
        self.assertEqual(self.Audit.search_count([]), before + 1,
                         "and nothing else was logged")

    def test_manager_can_sign(self):
        contract = self._contract()
        contract.with_user(self.manager).write({'state': 'signed_client'})
        contract.invalidate_recordset(['state'])
        self.assertEqual(contract.state, 'signed_client')

        rows = self.Audit.search([
            ('stage', '=', 'sign_client'), ('res_id', '=', contract.id)])
        self.assertEqual(rows.approver_id, self.manager)
        self.assertEqual(rows.matched_group_id, self.team_lead_group,
                         "a manager matches on the team-lead group, which the chain implies")

    def test_signing_an_already_signed_contract_is_not_a_second_approval(self):
        """Re-writing the state a contract already holds is not a new signature.

        Without this carve-out an ordinary salesperson could not make any edit to a signed
        contract whose write happened to include `state`, and every such write would add a
        spurious audit row.
        """
        contract = self._contract()
        contract.with_user(self.team_lead).write({'state': 'signed_client'})
        rows_after_signing = self.Audit.search_count([
            ('stage', '=', 'sign_client'), ('res_id', '=', contract.id)])

        contract.with_user(self.salesperson).write({'state': 'signed_client'})
        self.assertEqual(
            self.Audit.search_count([('stage', '=', 'sign_client'), ('res_id', '=', contract.id)]),
            rows_after_signing,
            "a no-op state write must not be gated and must not log a second approval")

    # -- the S7 behaviours this inherits ----------------------------------------------------
    def test_stage_off_skips_gate(self):
        """S7's master switch skips this stage like every other one.

        **Asserted, not assumed, because it weakens the gate**: with `approval_enabled = False`
        an ordinary salesperson can sign again. That is `_user_can_approve()` returning True for
        everyone when approvals are off (approval_gate_mixin.py:38-39) - the S7 design, not
        something this change introduced. It is recorded in the decisions log as a consequence
        the owner must accept, the alternative being to move `sign_client` into
        NON_CONFIGURABLE_GATES and make it the first stage exempt from the switch.
        """
        self.company.approval_enabled = False
        contract = self._contract()

        self.assertTrue(contract.with_user(self.salesperson)._user_can_approve('sign_client'),
                        "with approvals off the stage must be skipped, like the others")
        contract.with_user(self.salesperson).write({'state': 'signed_client'})
        contract.invalidate_recordset(['state'])
        self.assertEqual(contract.state, 'signed_client',
                         "so a salesperson CAN sign while approvals are off - by design, and "
                         "the owner must accept it")

    def test_empty_group_refused_when_approval_on(self):
        """A signing stage with no group must never silently allow.

        Two halves, because with approvals on the ORM makes the unsafe state unreachable:

        1. Emptying the stage while approvals are on is refused by S7's own constrains, so the
           configuration cannot be left unsatisfiable in the first place.
        2. The gate's own "no group configured" branch refuses rather than allowing. Shown on
           `operation_manager`, which genuinely ships with no default and no python gate, so it
           is the one stage that really is empty with approvals on - the branch is shared, so
           this exercises the same code path `sign_client` would take.
        """
        self.assertTrue(self.company.approval_enabled)

        # In a savepoint: the constrains fires *after* the write lands, so without one the
        # rolled-back value would still be in the cursor for the rest of this test.
        with self.assertRaises(ValidationError) as caught, self.env.cr.savepoint():
            self.company.write({'sign_client_group_ids': [(5, 0, 0)]})
        self.assertIn('Sign by Client', str(caught.exception),
                      "the refusal must name the stage left without a group")
        self.assertEqual(self.company._approver_groups('sign_client'), self.team_lead_group,
                         "and the configuration is unchanged after the refusal")

        self.assertFalse(self.company._approver_groups('operation_manager'),
                         "fixture check: operation_manager ships empty")
        contract = self._contract()
        with self.assertRaises(UserError) as caught:
            contract.with_user(self.salesperson)._user_can_approve('operation_manager')
        self.assertIn('No approver group is configured', str(caught.exception),
                      "an unconfigured stage must refuse loudly, never allow silently")

    # -- the structural guard ---------------------------------------------------------------
    def test_no_unguarded_signing_write(self):
        """Every write of a signing state or the client-signature flag must pass the gate.

        A source sweep rather than a behavioural test, because the gate lives in `write()`: any
        future code that sets these values is covered automatically *unless* it bypasses the ORM
        or re-implements `write()`. This fails on the two shapes that would do that - a direct
        `self._write(...)`/SQL write, and a `write()` override on `sale.proposal` in another
        module that does not call `super()`.

        Assignments and `write()` calls are both fine: they go through `sale.proposal.write()`,
        which is the gate. What is swept for is the ways around it.
        """
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        targets = set(SIGNING_STATES) | {'signed_by_client'}
        offenders = []

        for dirpath, _dirs, files in os.walk(os.path.join(root, 'models')):
            if '__pycache__' in dirpath:
                continue
            for filename in sorted(files):
                if not filename.endswith('.py'):
                    continue
                path = os.path.join(dirpath, filename)
                source = open(path, encoding='utf-8').read()
                rel = os.path.relpath(path, root)

                # (a) a low-level write that skips write() entirely, on a line that also
                #     mentions one of the signing values
                for lineno, line in enumerate(source.split('\n'), 1):
                    if not any(t in line for t in targets):
                        continue
                    if '_write(' in line or 'execute(' in line or 'flush_recordset' in line:
                        offenders.append('%s:%d bypasses write(): %s'
                                         % (rel, lineno, line.strip()[:70]))

                # (b) a write() override on sale.proposal that never calls super()
                try:
                    tree = ast.parse(source)
                except SyntaxError:                                   # pragma: no cover
                    continue
                for node in ast.walk(tree):
                    if not isinstance(node, ast.ClassDef):
                        continue
                    names = {
                        stmt.value.value
                        for stmt in node.body
                        if isinstance(stmt, ast.Assign)
                        and isinstance(stmt.value, ast.Constant)
                        and any(getattr(t, 'id', '') in ('_name', '_inherit')
                                for t in stmt.targets)
                    }
                    if 'sale.proposal' not in names:
                        continue
                    for stmt in node.body:
                        if not (isinstance(stmt, ast.FunctionDef) and stmt.name == 'write'):
                            continue
                        calls_super = any(
                            isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                            and n.func.attr == 'write'
                            and isinstance(n.func.value, ast.Call)
                            and getattr(n.func.value.func, 'id', '') == 'super'
                            for n in ast.walk(stmt))
                        if not calls_super:
                            offenders.append(
                                '%s:%d write() override on sale.proposal without super()'
                                % (rel, stmt.lineno))

        self.assertFalse(
            offenders,
            "every signing write must go through sale.proposal.write(), where the "
            "`sign_client` gate lives; found:\n%s" % '\n'.join(offenders))

    def test_the_gate_covers_every_signing_state(self):
        """SIGNING_STATES must list every state whose label says the sale was signed.

        Guards against a new signing state being added to the selection and quietly escaping
        the gate - the failure mode the audit found for the state field as a whole.
        """
        selection = dict(self.env['sale.proposal']._fields['state'].selection)
        signed_looking = {
            value for value, label in selection.items()
            if 'sign' in value or 'Signed' in label}
        self.assertEqual(
            signed_looking, set(SIGNING_STATES),
            "a signing state exists that SIGNING_STATES does not cover, so write() would not "
            "gate it: %s" % (signed_looking - set(SIGNING_STATES)))
