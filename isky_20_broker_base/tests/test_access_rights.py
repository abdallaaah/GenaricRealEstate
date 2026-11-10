from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'broker_access')
class TestBrokerAccessStructure(TransactionCase):
    """Structural guarantees over whatever isky_20_broker_* modules are installed.

    These scan ir.access itself, so a module added later that violates P1 (an
    everyone-CRUD row on a business model) fails the suite without a new test.
    """

    def _broker_models(self):
        """Concrete, non-transient models defined by installed isky_20_broker modules."""
        self.env.cr.execute("""
            SELECT DISTINCT d.res_id
            FROM ir_model_data d
            WHERE d.model = 'ir.model' AND d.module LIKE 'isky_20_broker%'
        """)
        model_ids = [row[0] for row in self.env.cr.fetchall()]
        models = self.env['ir.model'].browse(model_ids).exists()
        result = self.env['ir.model']
        for model in models:
            registry_model = self.env.registry.get(model.model)
            if registry_model is None or registry_model._transient or registry_model._abstract:
                continue
            result |= model
        return result

    def test_every_broker_model_has_an_access_row(self):
        missing = []
        for model in self._broker_models():
            rows = self.env['ir.access'].sudo().search([
                ('model_id', '=', model.id), ('active', '=', True), ('group_id', '!=', False),
            ])
            if not rows:
                missing.append(model.model)
        self.assertFalse(missing, f"Broker models with no active permission row: {missing}")

    def test_no_row_grants_crud_to_every_user(self):
        """P1: no business model hands full CRUD with no domain to all internal users."""
        offenders = self.env['ir.access'].sudo().search([
            ('active', '=', True),
            ('group_id', '=', self.env.ref('base.group_user').id),
            ('operation', '=', 'crud'),
            ('domain', 'in', [False, '', '[]']),
        ]).filtered(lambda a: a.model_id.model in self._broker_models().mapped('model')
                    and not self.env.registry[a.model_id.model]._transient)
        self.assertFalse(
            offenders.mapped('model_id.model'),
            "Active base.group_user crud rows with no domain on broker business models")

    def test_broker_admin_does_not_imply_system(self):
        """D12: the functional broker admin must not escalate to Settings/system."""
        admin_group = self.env.ref('isky_20_broker_base.group_broker_admin')
        implied_closure = admin_group
        todo = admin_group
        while todo:
            todo = todo.implied_ids - implied_closure
            implied_closure |= todo
        self.assertNotIn(self.env.ref('base.group_system'), implied_closure)
        self.assertNotIn(self.env.ref('base.group_erp_manager'), implied_closure)

    def test_operations_ladder_split(self):
        """D1: operations manager implies executive + approver, and no sales-track group."""
        ops_manager = self.env.ref('isky_20_broker_crm.group_operation_manager')
        implied = ops_manager
        todo = ops_manager
        while todo:
            todo = todo.implied_ids - implied
            implied |= todo
        self.assertIn(self.env.ref('isky_20_broker_crm.group_operation_executive'), implied)
        self.assertIn(self.env.ref('isky_20_broker_base.group_permission_approver'), implied)
        self.assertNotIn(self.env.ref('isky_20_broker_crm.group_director_manager'), implied)
        self.assertNotIn(self.env.ref('sales_team.group_sale_manager'), implied)
        self.assertNotIn(self.env.ref('sales_team.group_sale_salesman'), implied)
