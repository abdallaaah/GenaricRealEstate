from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'broker_access')
class TestPermissionRequestAccess(TransactionCase):
    """D9: only the approver group decides, never on its own requests, and only
    through the two actions. D8: portal users reach no broker model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, no_reset_password=True, mail_create_nolog=True))

        def user(login, groups):
            return cls.env['res.users'].create({
                'name': login, 'login': login,
                'group_ids': [(6, 0, [cls.env.ref(g).id for g in groups])]})

        cls.requester = user('pr_requester', ['base.group_user'])
        cls.approver = user('pr_approver', [
            'base.group_user', 'isky_20_broker_base.group_permission_approver'])
        cls.approver_requester = user('pr_both', [
            'base.group_user', 'isky_20_broker_base.group_permission_approver'])
        cls.portal_user = cls.env['res.users'].create({
            'name': 'portal_u', 'login': 'portal_u',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})

        cls.request = cls.env['permission.request'].with_user(cls.requester).create({
            'name': 'REQ-T1', 'request_type': 'lead', 'client_name': 'Client X'})

    def test_non_approver_cannot_decide(self):
        with self.assertRaises(AccessError):
            self.request.with_user(self.requester).action_approve()

    def test_approver_decides(self):
        self.request.with_user(self.approver).action_approve()
        self.assertEqual(self.request.approval_status, 'approved')

    def test_requester_cannot_decide_own_even_in_group(self):
        own = self.env['permission.request'].with_user(self.approver_requester).create({
            'name': 'REQ-T2', 'request_type': 'unit'})
        with self.assertRaises(AccessError):
            own.with_user(self.approver_requester).action_approve()
        with self.assertRaises(AccessError):
            own.with_user(self.approver_requester).action_reject()

    def test_status_moves_only_through_the_actions(self):
        with self.assertRaises(AccessError):
            self.request.with_user(self.approver).write({'approval_status': 'approved'})

    def test_portal_has_no_access_to_broker_models(self):
        """D8/P2: every broker business model refuses a portal user over the ORM (RPC path)."""
        for model_name in ('crm.lead', 'broker.unit', 'permission.request',
                           'developer.project', 'project.sale.phase', 'user.notification',
                           'broker.approval.rule', 'lead.stage'):
            Model = self.env[model_name].with_user(self.portal_user)
            with self.assertRaises(AccessError, msg=f"portal read on {model_name} must fail"):
                Model.search([], limit=1)
            with self.assertRaises(AccessError, msg=f"portal create on {model_name} must fail"):
                Model.create({})
