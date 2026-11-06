import ast
import os

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

SC = 'isky_18_realestate_developer_sales_crm'
MGR = '%s.sales_manager_group' % SC


@tagged('post_install', '-at_install')
class TestAcl122(TransactionCase):
    """Open question 12.2: this module shipped no access rules for its own models, so no
    ordinary user could touch installments, EOIs or contracts at all.

    Every test here runs `with_user(...)`. Odoo tests run as superuser by default, which
    bypasses ACLs entirely - so a test that did not switch user would pass no matter what the
    rules said, which is exactly why this gap survived three phases.
    """

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.user = self.env['res.users'].create({
            'name': 'acl_plain', 'login': 'acl_plain',
            'company_id': self.company.id, 'company_ids': [(6, 0, [self.company.id])],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]})
        self.manager = self.env['res.users'].create({
            'name': 'acl_mgr', 'login': 'acl_mgr',
            'company_id': self.company.id, 'company_ids': [(6, 0, [self.company.id])],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref(MGR).id])]})
        self.partner = self.env['res.partner'].create({
            'name': 'ACL Customer', 'national_id': 'ACL-1'})
        self.project = self.env['realestate.project'].create({
            'name': 'ACL Project', 'abbreviation': 'ACLP'})

    # -- the point of 12.2 -----------------------------------------------------------------
    def test_internal_user_can_run_the_core_flow(self):
        """An ordinary internal user can create a reservation, a contract and installment
        lines. Before 12.2 every one of these raised AccessError."""
        res = self.env['real.estate.sale.reservation'].with_user(self.user).create({
            'customer_id': self.partner.id, 'company_id': self.company.id,
            'project_id': self.project.id})
        self.assertTrue(res.id)

        eoi = self.env['eoi.eoi'].with_user(self.user).create({
            'customer_id': self.partner.id, 'company_id': self.company.id})
        self.assertTrue(eoi.id)

        contract = self.env['sale.proposal'].with_user(self.user).create({
            'customer_id': self.partner.id, 'company_id': self.company.id,
            'sale_contract_reservation_id': res.id})
        self.assertTrue(contract.id)

        line = self.env['installment.lines'].with_user(self.user).create({
            'name': 'ACL line', 'amount': 1000.0, 'serial': 1,
            'reservation_id': res.id})
        self.assertTrue(line.id)
        line.with_user(self.user).write({'amount': 1200.0})
        self.assertEqual(line.amount, 1200.0)

    def test_internal_user_can_delete_recompute_children(self):
        """The installment builders delete and recreate lines, and the reallocation engine
        unlinks payment allocations - both run as the user, so unlink has to be granted on
        those children or recalculation breaks."""
        res = self.env['real.estate.sale.reservation'].with_user(self.user).create({
            'customer_id': self.partner.id, 'company_id': self.company.id,
            'project_id': self.project.id})
        line = self.env['installment.lines'].with_user(self.user).create({
            'name': 'ACL del', 'amount': 500.0, 'serial': 1, 'reservation_id': res.id})
        line.with_user(self.user).unlink()
        self.assertFalse(line.exists())

    def test_plain_user_cannot_delete_a_document(self):
        """Top-level documents are manager-only to delete."""
        res = self.env['real.estate.sale.reservation'].with_user(self.user).create({
            'customer_id': self.partner.id, 'company_id': self.company.id,
            'project_id': self.project.id})
        with self.assertRaises(AccessError):
            res.with_user(self.user).unlink()
        res.with_user(self.manager).unlink()
        self.assertFalse(res.exists())

    def test_config_models_are_read_only_for_plain_users(self):
        stage = self.env['lead.stage'].create({'name': 'ACL Stage'})
        self.assertTrue(stage.with_user(self.user).name, "a user must be able to read config")
        with self.assertRaises(AccessError):
            self.env['lead.stage'].with_user(self.user).create({'name': 'nope'})
        created = self.env['lead.stage'].with_user(self.manager).create({'name': 'ACL Stage 2'})
        self.assertTrue(created.id, "a manager maintains configuration")

    def test_approval_step_is_now_reachable_without_granting_acls(self):
        """The S7 approval-audit test had to create ir.model.access rows in-transaction because
        a non-superuser could not write sale.proposal at all. That workaround is no longer
        needed - which is the concrete payoff of 12.2."""
        group = self.env.ref('%s.group_manager_approval' % SC)
        approver = self.env['res.users'].create({
            'name': 'acl_approver', 'login': 'acl_approver',
            'company_id': self.company.id, 'company_ids': [(6, 0, [self.company.id])],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, group.id])]})
        contract = self.env['sale.proposal'].with_user(self.user).create({
            'customer_id': self.partner.id, 'company_id': self.company.id})
        Audit = self.env['realestate.approval.audit']
        before = Audit.search_count([('entry_type', '=', 'approval')])
        contract.with_user(approver).write({'manager_approve': True})
        self.assertEqual(Audit.search_count([('entry_type', '=', 'approval')]), before + 1,
                         "the approval wrote its audit row, as a real user")

    def test_audit_trail_is_append_only_for_users(self):
        """S7's rule: a user may create and read audit rows, never edit or delete them."""
        row = self.env['realestate.approval.audit'].with_user(self.user).create({
            'entry_type': 'config', 'company_id': self.company.id,
            'field_name': 'x', 'old_value': 'a', 'new_value': 'b'})
        self.assertTrue(row.id)
        with self.assertRaises(AccessError):
            row.with_user(self.user).write({'new_value': 'tampered'})
        with self.assertRaises(AccessError):
            row.with_user(self.user).unlink()

    # -- the regression guard --------------------------------------------------------------
    def test_every_model_has_an_acl_row(self):
        """The guard that stops 12.2 happening again: every model this module declares must
        have at least one ACL row. crm.lead is excluded - core `crm` owns it, and this module
        only sets _name on it to inject a mixin (Phase 4)."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        core_owned = {'crm.lead'}

        declared, abstract = set(), set()
        for sub in ('models', 'wizard'):
            for dp, _dirs, files in os.walk(os.path.join(root, sub)):
                if '__pycache__' in dp:
                    continue
                for fn in files:
                    if not fn.endswith('.py'):
                        continue
                    tree = ast.parse(open(os.path.join(dp, fn), encoding='utf-8').read())
                    for node in ast.walk(tree):
                        if not isinstance(node, ast.ClassDef):
                            continue
                        bases = ' '.join(ast.unparse(b) for b in node.bases)
                        for st in node.body:
                            if not isinstance(st, ast.Assign):
                                continue
                            for t in st.targets:
                                if (isinstance(t, ast.Name) and t.id == '_name'
                                        and isinstance(st.value, ast.Constant)):
                                    target = abstract if 'Abstract' in bases else declared
                                    target.add(st.value.value)

        covered = set()
        csv_path = os.path.join(root, 'security', 'ir.model.access.csv')
        for line in open(csv_path, encoding='utf-8'):
            if line.startswith('#') or line.startswith('id,'):
                continue
            parts = line.strip().split(',')
            if len(parts) > 2 and parts[2].startswith('model_'):
                covered.add(parts[2][len('model_'):])

        missing = sorted(
            m for m in (declared - abstract - core_owned)
            if m.replace('.', '_') not in covered)
        self.assertFalse(
            missing,
            "these models have no ir.model.access row, so no ordinary user can use them:\n%s"
            % '\n'.join('  - %s' % m for m in missing))

    def test_no_acl_row_grants_access_to_every_user(self):
        """An ACL row with an empty group applies to EVERY user, portal and public included.
        unit_inventory and commission do that 28 and 9 times; this module must not."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        csv_path = os.path.join(root, 'security', 'ir.model.access.csv')
        blanket = []
        for lineno, line in enumerate(open(csv_path, encoding='utf-8'), 1):
            if line.startswith('#') or line.startswith('id,') or not line.strip():
                continue
            parts = line.strip().split(',')
            if len(parts) >= 4 and not parts[3].strip():
                blanket.append('%s:%d %s' % (os.path.basename(csv_path), lineno, parts[0]))
        self.assertFalse(blanket, "ACL rows with no group grant access to all users:\n%s"
                                  % '\n'.join(blanket))
