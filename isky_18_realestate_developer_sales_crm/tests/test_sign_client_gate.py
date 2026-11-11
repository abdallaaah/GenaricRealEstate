import ast
import os

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from ..models.config.approval_settings import (
    APPROVAL_STAGES,
    NON_CONFIGURABLE_GATES,
)
from ..models.core.sale_proposal import SIGNING_STATES

SC = 'isky_18_realestate_developer_sales_crm'


@tagged('post_install', '-at_install')
class TestSignClientGate(TransactionCase):
    """The signing gate: only the Director group may move a sale into a signed state,
    whether or not approvals are enabled.

    History, because this file changed rules once already: the 2026-11-08 version gated
    signing behind the S7 `sign_client` stage, defaulting to Sales Team Lead, and inherited
    S7's behaviour that `approval_enabled = False` skips every stage. The owner's 2026-11-10
    decision (SG-D1..D4 in the decisions log) replaced that: ONE group signs everything -
    `director_manager_group` - the gate is in NON_CONFIGURABLE_GATES, and the approvals
    switch no longer skips it. The tests that said "team lead can sign" and "stage off skips
    the gate" are superseded by that decision, not weakened: their replacements below assert
    the exact opposite, as the owner instructed.

    Every test acts as a real user through `with_user(...)`. Odoo tests otherwise run as
    superuser, which bypasses both ACLs and the gate's `has_group()` check, so a test
    without `with_user` would pass whatever the gate said - 12.2's lesson, applied here.
    """

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.partner = self.env['res.partner'].create({
            'name': 'SC Gate Customer', 'national_id': 'SCG-NID-0001'})
        self.team_lead_group = self.env.ref('%s.sales_team_lead_group' % SC)
        self.manager_group = self.env.ref('%s.sales_manager_group' % SC)
        self.director_group = self.env.ref('%s.director_manager_group' % SC)
        self.salesman_group = self.env.ref('sales_team.group_sale_salesman')
        self.Audit = self.env['realestate.approval.audit']

        # The four actors. All internal, all holding the base sales rights that let them
        # reach a contract at all: sale.proposal grants base.group_user 1,1,1,0 (12.2), so
        # write access is not what separates them - only the signing group is.
        self.salesperson = self._user('scg_sales', [self.salesman_group])
        self.team_lead = self._user('scg_lead', [self.team_lead_group])
        self.manager = self._user('scg_manager', [self.manager_group])
        self.director = self._user('scg_director', [self.director_group])

    def _user(self, login, groups=()):
        return self.env['res.users'].create({
            'name': login, 'login': login, 'email': '%s@example.com' % login,
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id] + [g.id for g in groups])]})

    def _contract(self):
        """A contract in `draft`, with no unit and no installments.

        Deliberately bare: writing `signed_client` on a contract that has a unit also marks
        the unit sold, and a contract with collected installments would start a commission.
        Neither belongs in a test about who may sign.
        """
        return self.env['sale.proposal'].create({
            'customer_id': self.partner.id, 'company_id': self.company.id})

    # -- the wiring the decisions require (SG-D1..D4) --------------------------------------
    def test_group_chain_unchanged(self):
        """SG-D4: `sales_team_lead_group` keeps its place in the chain; only signing moved.

        salesman <- team lead <- sales manager <- sector manager <- director, resolved
        through the users rather than read off the records.
        """
        self.assertIn(self.salesman_group, self.team_lead_group.implied_ids)
        self.assertIn(self.team_lead_group, self.manager_group.implied_ids)
        self.assertTrue(self.director.has_group('%s.sales_team_lead_group' % SC),
                        "a director holds the team-lead group through the implied chain")
        self.assertFalse(self.team_lead.has_group('%s.director_manager_group' % SC),
                         "the chain must not run backwards - a team lead is not a director")
        self.assertFalse(self.manager.has_group('%s.director_manager_group' % SC),
                         "nor is a sales manager")

    def test_signing_not_configurable(self):
        """SG-D2/SG-D3: the signing gates live in NON_CONFIGURABLE_GATES, point at the
        Director group, and offer no company setting to change that."""
        self.assertEqual(NON_CONFIGURABLE_GATES['sign_client'],
                         '%s.director_manager_group' % SC)
        self.assertEqual(NON_CONFIGURABLE_GATES['sign_ceo'],
                         '%s.director_manager_group' % SC)
        self.assertNotIn('sign_client', APPROVAL_STAGES,
                         "the stage must be OUT of the configurable registry")
        self.assertNotIn('sign_ceo', APPROVAL_STAGES)
        self.assertNotIn('sign_client_group_ids', self.env['res.company']._fields,
                         "the company field is gone - the group is edited, not configured")
        self.assertNotIn('sign_client_group_ids', self.env['res.config.settings']._fields,
                         "and Sales Setup no longer offers it")
        self.assertNotIn('sign_ceo_group_ids', self.env['res.config.settings']._fields)

    # -- who can sign ----------------------------------------------------------------------
    def test_director_can_sign_client_and_ceo(self):
        """The Director signs both states; each signature writes one audit row naming the
        gate and the matched group."""
        for state, gate in (('signed_client', 'sign_client'), ('signed_ceo', 'sign_ceo')):
            contract = self._contract()
            contract.with_user(self.director).write({'state': state})
            contract.invalidate_recordset(['state'])
            self.assertEqual(contract.state, state)

            rows = self.Audit.search([
                ('entry_type', '=', 'approval'), ('stage', '=', gate),
                ('res_model', '=', 'sale.proposal'), ('res_id', '=', contract.id)])
            self.assertEqual(len(rows), 1, "exactly one audit row for %s" % state)
            self.assertEqual(rows.approver_id, self.director, "recording who signed")
            self.assertEqual(rows.matched_group_id, self.director_group,
                             "and the group that permits it")
            self.assertEqual(rows.company_id, self.company)
            self.assertTrue(rows.create_date)

    def test_director_can_set_signed_by_client_flag(self):
        contract = self._contract()
        contract.with_user(self.director).write({'signed_by_client': True})
        contract.invalidate_recordset(['signed_by_client'])
        self.assertTrue(contract.signed_by_client)

    # -- who cannot ------------------------------------------------------------------------
    def test_team_lead_cannot_sign(self):
        """SG-D1's consequence, asserted: the Sales Team Lead no longer signs."""
        contract = self._contract()
        with self.assertRaises(UserError) as caught:
            contract.with_user(self.team_lead).write({'state': 'signed_client'})
        self.assertIn('Sign by Client', str(caught.exception),
                      "the refusal must name the step")
        contract.invalidate_recordset(['state'])
        self.assertEqual(contract.state, 'draft', "the state must not have moved")

        with self.assertRaises(UserError):
            contract.with_user(self.team_lead).write({'signed_by_client': True})

    def test_manager_cannot_sign(self):
        contract = self._contract()
        with self.assertRaises(UserError) as caught:
            contract.with_user(self.manager).write({'state': 'signed_ceo'})
        self.assertIn('Sign by CEO', str(caught.exception))
        contract.invalidate_recordset(['state'])
        self.assertEqual(contract.state, 'draft')

    def test_salesperson_cannot_sign(self):
        contract = self._contract()
        for vals in ({'state': 'signed_client'}, {'state': 'signed_ceo'},
                     {'signed_by_client': True}):
            with self.assertRaises(UserError):
                contract.with_user(self.salesperson).write(dict(vals))
        contract.invalidate_recordset(['state', 'signed_by_client'])
        self.assertEqual(contract.state, 'draft')
        self.assertFalse(contract.signed_by_client)

    def test_approvals_off_still_enforced(self):
        """SG-D2: the approvals switch no longer skips signing.

        This replaces 2026-11-08's `test_stage_off_skips_gate`, which asserted the opposite
        (S7 behaviour: a salesperson could sign with approvals off). The owner's 2026-11-10
        decision made signing the explicit exception to S7 decision 2, so the expectation
        flips: refused for everyone outside the group, allowed for the Director, with the
        switch in either position.
        """
        self.company.approval_enabled = False
        contract = self._contract()

        for user in (self.salesperson, self.team_lead, self.manager):
            for vals in ({'state': 'signed_client'}, {'state': 'signed_ceo'},
                         {'signed_by_client': True}):
                with self.assertRaises(UserError):
                    contract.with_user(user).write(dict(vals))
        contract.invalidate_recordset(['state'])
        self.assertEqual(contract.state, 'draft',
                         "nothing may have moved while approvals were off")

        contract.with_user(self.director).write({'state': 'signed_client'})
        contract.invalidate_recordset(['state'])
        self.assertEqual(contract.state, 'signed_client',
                         "and the Director still signs with the switch off")

    def test_signing_an_already_signed_contract_is_not_a_second_approval(self):
        """The SC-D3 carve-out survives the rewrite: re-writing the state a contract already
        holds is not a new signature - not gated, not logged. Without it, a salesperson
        could not make any edit to a signed contract whose write happened to include
        `state`."""
        contract = self._contract()
        contract.with_user(self.director).write({'state': 'signed_client'})
        rows_after_signing = self.Audit.search_count([
            ('stage', '=', 'sign_client'), ('res_id', '=', contract.id)])

        contract.with_user(self.salesperson).write({'state': 'signed_client'})
        self.assertEqual(
            self.Audit.search_count([('stage', '=', 'sign_client'), ('res_id', '=', contract.id)]),
            rows_after_signing,
            "a no-op state write must not be gated and must not log a second approval")

    # -- the structural guards --------------------------------------------------------------
    def test_source_sweep_for_signing_states(self):
        """Every write of a signing state or the client-signature flag must pass the gate.

        The gate lives in `write()`, so assignments and `write()` calls are covered
        automatically. What this sweeps for is the two ways around it: a low-level
        `_write(...)`/SQL write naming a signing value, and a `write()` override on
        `sale.proposal` in this module that does not call `super()`.
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

                for lineno, line in enumerate(source.split('\n'), 1):
                    if not any(t in line for t in targets):
                        continue
                    if '_write(' in line or 'execute(' in line or 'flush_recordset' in line:
                        offenders.append('%s:%d bypasses write(): %s'
                                         % (rel, lineno, line.strip()[:70]))

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
            "every signing write must go through sale.proposal.write(), where the signing "
            "gate lives; found:\n%s" % '\n'.join(offenders))

    def test_the_gate_covers_every_signing_state(self):
        """SIGNING_STATES must map every state whose label says the sale was signed.

        Guards against a new signing state being added to the selection and quietly escaping
        the gate - the failure mode the 2026-11-08 audit found for the state field as a
        whole. Also pins that every mapped gate actually exists in NON_CONFIGURABLE_GATES,
        so the mapping cannot point at a gate that nothing enforces.
        """
        selection = dict(self.env['sale.proposal']._fields['state'].selection)
        signed_looking = {
            value for value, label in selection.items()
            if 'sign' in value or 'Signed' in label}
        self.assertEqual(
            signed_looking, set(SIGNING_STATES),
            "a signing state exists that SIGNING_STATES does not cover: %s"
            % (signed_looking - set(SIGNING_STATES)))
        for state, gate in SIGNING_STATES.items():
            self.assertIn(gate, NON_CONFIGURABLE_GATES,
                          "state %s maps to gate %s, which is not enforced" % (state, gate))
