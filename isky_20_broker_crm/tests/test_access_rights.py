from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'broker_access')
class TestBrokerLeadAccess(TransactionCase):
    """D2/D3/D4/D5: lead visibility, delete policy, approval checkpoints, finance gates.
    Every behavioural assertion runs with_user (P6)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, no_reset_password=True, mail_create_nolog=True))
        cls.company = cls.env.company
        cls.company.broker_unassigned_leads_visible_to_all = False
        cls.company_b = cls.env['res.company'].create({'name': 'Broker Co B'})

        def user(login, groups):
            return cls.env['res.users'].create({
                'name': login, 'login': login,
                'group_ids': [(6, 0, [cls.env.ref(g).id for g in groups])],
                'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])],
            })

        cls.salesperson = user('sp1', ['sales_team.group_sale_salesman'])
        cls.salesperson2 = user('sp2', ['sales_team.group_sale_salesman'])
        cls.team_leader = user('tl', ['sales_team.group_sale_salesman'])
        cls.sales_manager = user('sm', ['sales_team.group_sale_manager'])
        cls.ops_exec = user('ops_exec', ['isky_20_broker_crm.group_operation_executive'])
        cls.ops_manager = user('ops_mgr', ['isky_20_broker_crm.group_operation_manager'])
        cls.lead_admin = user('lead_admin', [
            'sales_team.group_sale_salesman', 'isky_20_broker_crm.group_lead_admin'])
        cls.finance = user('finance', [
            'sales_team.group_sale_salesman', 'isky_20_broker_crm.group_finance'])
        cls.plain_user = user('plain', ['base.group_user'])

        cls.team = cls.env['crm.team'].create({
            'name': 'Team Alpha', 'user_id': cls.team_leader.id,
            'member_ids': [(4, cls.salesperson.id)],
        })
        cls.Lead = cls.env['crm.lead']
        cls.own_lead = cls.Lead.create({
            'name': 'own', 'type': 'opportunity', 'user_id': cls.salesperson.id,
            'team_id': cls.team.id, 'company_id': cls.company.id})
        cls.other_lead = cls.Lead.create({
            'name': 'other', 'type': 'opportunity', 'user_id': cls.salesperson2.id,
            'team_id': False, 'company_id': cls.company.id})
        cls.unassigned_lead = cls.Lead.create({
            'name': 'pool', 'type': 'opportunity', 'user_id': False,
            'team_id': cls.team.id, 'company_id': cls.company.id})

    def _visible(self, user, lead):
        return lead in self.Lead.with_user(user).search([('id', 'in', (
            self.own_lead | self.other_lead | self.unassigned_lead).ids)])

    # ---------------------------------------------------------------- D2 visibility

    def test_salesperson_sees_own_not_colleague_not_pool(self):
        self.assertTrue(self._visible(self.salesperson, self.own_lead))
        self.assertFalse(self._visible(self.salesperson, self.other_lead))
        self.assertFalse(self._visible(self.salesperson, self.unassigned_lead),
                         "setting off: plain salesperson must not see the unassigned pool")

    def test_split_deal_participant_sees_lead(self):
        self.other_lead.with_user(self.sales_manager).write({'sales_ids': [(4, self.salesperson.id)]})
        self.assertTrue(self._visible(self.salesperson, self.other_lead))

    def test_pool_setting_turns_on_without_restart(self):
        self.assertFalse(self._visible(self.salesperson, self.unassigned_lead))
        self.company.broker_unassigned_leads_visible_to_all = True
        self.assertTrue(self._visible(self.salesperson, self.unassigned_lead),
                        "setting on must apply immediately, no restart")
        self.company.broker_unassigned_leads_visible_to_all = False
        self.assertFalse(self._visible(self.salesperson, self.unassigned_lead))

    def test_team_leader_sees_team_leads_and_team_pool(self):
        self.assertTrue(self._visible(self.team_leader, self.own_lead))
        self.assertTrue(self._visible(self.team_leader, self.unassigned_lead),
                        "the team's unassigned leads stay visible to its leader with the pool off")
        self.assertFalse(self._visible(self.team_leader, self.other_lead))

    def test_manager_and_ops_see_all(self):
        for boss in (self.sales_manager, self.ops_exec, self.ops_manager, self.lead_admin):
            for lead in (self.own_lead, self.other_lead, self.unassigned_lead):
                self.assertTrue(self._visible(boss, lead), f"{boss.login} must see {lead.name}")

    def test_ops_exec_reads_but_cannot_write(self):
        self.own_lead.with_user(self.ops_exec).read(['name'])
        with self.assertRaises(AccessError):
            self.own_lead.with_user(self.ops_exec).write({'description': 'nope'})

    def test_ops_manager_can_write(self):
        self.own_lead.with_user(self.ops_manager).write({'description': 'ops note'})
        self.assertEqual(self.own_lead.description, '<p>ops note</p>')

    def test_commission_upline_reads_only(self):
        upline = self.env['res.users'].create({
            'name': 'upline', 'login': 'upline',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
            'company_id': self.company.id, 'company_ids': [(6, 0, [self.company.id])]})
        self.env['commission.commission'].sudo().create({
            'opportunity_id': self.other_lead.id, 'employee_id': upline.id})
        self.assertTrue(self._visible(upline, self.other_lead))
        with self.assertRaises(AccessError):
            self.other_lead.with_user(upline).write({'description': 'nope'})

    def test_company_isolation(self):
        lead_b = self.Lead.sudo().create({
            'name': 'b-lead', 'type': 'opportunity', 'user_id': False, 'company_id': self.company_b.id})
        self.assertNotIn(lead_b, self.Lead.with_user(self.sales_manager).search([('name', '=', 'b-lead')]),
                         "user of company A must not read company B leads")

    # ---------------------------------------------------------------- D3 delete

    def test_sales_manager_cannot_delete_lead_admin_can(self):
        with self.assertRaises(AccessError):
            self.other_lead.with_user(self.sales_manager).unlink()
        doomed = self.Lead.create({'name': 'doomed', 'type': 'opportunity',
                                   'user_id': self.salesperson.id, 'company_id': self.company.id})
        doomed.with_user(self.lead_admin).unlink()
        self.assertFalse(doomed.exists())

    def test_merge_works_for_lead_admin(self):
        dup1 = self.Lead.create({'name': 'dup', 'type': 'opportunity',
                                 'user_id': self.salesperson.id, 'company_id': self.company.id})
        dup2 = self.Lead.create({'name': 'dup', 'type': 'opportunity',
                                 'user_id': self.salesperson.id, 'company_id': self.company.id})
        wizard = self.env['crm.merge.opportunity'].with_user(self.lead_admin).create({
            'opportunity_ids': [(6, 0, (dup1 | dup2).ids)]})
        wizard.action_merge()
        self.assertEqual(len((dup1 | dup2).exists()), 1, "merge must fold one duplicate away")

    # ---------------------------------------------------------------- D4 checkpoints

    def _set_sales_rule(self):
        self.env['broker.approval.rule'].sudo().search([]).unlink()
        self.env['broker.approval.rule'].sudo().create({
            'phase': 'eoi', 'role': 'sales',
            'group_id': self.env.ref('sales_team.group_sale_salesman').id})

    def test_sales_checkpoint_requires_the_deal_salesperson(self):
        self._set_sales_rule()
        with self.assertRaises(AccessError):
            self.own_lead.with_user(self.sales_manager).write({'eoi_status_for_sales': 'approved'})
        self.own_lead.with_user(self.salesperson).write({'eoi_status_for_sales': 'approved'})
        self.assertEqual(self.own_lead.eoi_status_for_sales, 'approved')

    def test_sales_checkpoint_allows_split_participant(self):
        self._set_sales_rule()
        self.other_lead.with_user(self.sales_manager).write({'sales_ids': [(4, self.salesperson.id)]})
        self.other_lead.with_user(self.salesperson).write({'eoi_status_for_sales': 'approved'})
        self.assertEqual(self.other_lead.eoi_status_for_sales, 'approved')

    def test_approval_rules_admin_only(self):
        with self.assertRaises(AccessError):
            self.env['broker.approval.rule'].with_user(self.sales_manager).create({
                'phase': 'eoi', 'role': 'manager',
                'group_id': self.env.ref('sales_team.group_sale_manager').id})

    # ---------------------------------------------------------------- D5 finance gates

    def test_only_finance_reaches_collected(self):
        stage = self.env.ref('isky_20_broker_crm.stage_collected')
        with self.assertRaises(AccessError):
            self.own_lead.with_user(self.sales_manager).write({
                'stage_id': stage.id, 'collected_date': '2026-11-10'})
        self.own_lead.with_user(self.finance).write({
            'stage_id': stage.id, 'collected_date': '2026-11-10'})
        self.assertEqual(self.own_lead.stage_id, stage)

    def test_finance_gate_flag_off_opens_the_stage(self):
        """The finance gate is a feature flag: switched off, a non-finance user who can
        edit the deal may enter Collected -- the date requirement still applies."""
        self.env['broker.feature.flag']._set_flag(
            'crm_finance_stage_gate', "CRM: Finance Stage Gates", False, category='crm')
        try:
            stage = self.env.ref('isky_20_broker_crm.stage_collected')
            self.own_lead.with_user(self.sales_manager).write({
                'stage_id': stage.id, 'collected_date': '2026-11-10'})
            self.assertEqual(self.own_lead.stage_id, stage)
        finally:
            self.env['broker.feature.flag']._set_flag(
                'crm_finance_stage_gate', "CRM: Finance Stage Gates", True, category='crm')

    def test_reopen_gate_finance_or_ops_manager(self):
        cancel = self.env.ref('isky_20_broker_crm.stage_cancel')
        reopen = self.env.ref('isky_20_broker_crm.stage_reopen')
        lost_reason = self.env['crm.lost.reason'].sudo().create({'name': 'test'})
        self.other_lead.with_user(self.sales_manager).write({
            'stage_id': cancel.id, 'lost_reason_id': lost_reason.id})
        with self.assertRaises(AccessError):
            self.other_lead.with_user(self.sales_manager).write({
                'stage_id': reopen.id, 'reopen_reason': 'oops'})
        self.other_lead.with_user(self.ops_manager).write({
            'stage_id': reopen.id, 'reopen_reason': 'approved reopen'})
        self.assertEqual(self.other_lead.stage_id, reopen)

    # ---------------------------------------------------------------- D11 notifications

    def test_user_cannot_read_anothers_notifications(self):
        notification = self.env['user.notification'].sudo().create({
            'title': 'for sp1 only',
            'mail_message_id': self.env['mail.message'].sudo().create({
                'model': 'crm.lead', 'res_id': self.own_lead.id, 'body': 'x'}).id})
        self.env['partner.notification.rel'].sudo().create({
            'notification_id': notification.id, 'partner_id': self.salesperson.partner_id.id})
        Notification = self.env['user.notification']
        self.assertIn(notification, Notification.with_user(self.salesperson).search([]))
        self.assertNotIn(notification, Notification.with_user(self.salesperson2).search([]))
        with self.assertRaises(AccessError):
            notification.with_user(self.salesperson2).read(['title'])
