from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'broker_access')
class TestBrokerInventoryAccess(TransactionCase):
    """D7: projects/phases curated by the Inventory Manager; units editable by their
    assigned salesperson and that salesperson's team leader; prices and status are
    Inventory Manager-only; counters follow the unit's write access."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, no_reset_password=True, mail_create_nolog=True))

        def user(login, groups):
            return cls.env['res.users'].create({
                'name': login, 'login': login,
                'group_ids': [(6, 0, [cls.env.ref(g).id for g in groups])]})

        cls.salesperson = user('unit_sp1', ['sales_team.group_sale_salesman'])
        cls.salesperson2 = user('unit_sp2', ['sales_team.group_sale_salesman'])
        cls.team_leader = user('unit_tl', ['sales_team.group_sale_salesman'])
        cls.inventory_manager = user('unit_inv_mgr', [
            'base.group_user', 'isky_20_broker_real_estate.group_broker_unit_manager'])
        cls.plain = user('unit_plain', ['base.group_user'])

        cls.unit = cls.env['broker.unit'].create({
            'name': 'U-1', 'unit_purpose': 'to_sale', 'sale_price': 1_000_000,
            'seller_sales_person': cls.salesperson.id,
            'seller_team_leader': cls.team_leader.id,
        })

    # ---------------------------------------------------------------- units

    def test_everyone_reads_units(self):
        self.assertEqual(self.unit.with_user(self.plain).name, 'U-1',
                         "the inventory is shared: all internal users read units")

    def test_salesperson_edits_own_unit_not_anothers(self):
        self.unit.with_user(self.salesperson).write({'unit_number': '12A'})
        other_unit = self.env['broker.unit'].create({
            'name': 'U-2', 'unit_purpose': 'to_sale', 'sale_price': 500_000,
            'seller_sales_person': self.salesperson2.id})
        with self.assertRaises(AccessError):
            other_unit.with_user(self.salesperson).write({'unit_number': 'nope'})

    def test_team_leader_edits_members_unit(self):
        self.unit.with_user(self.team_leader).write({'unit_number': '12B'})
        self.assertEqual(self.unit.unit_number, '12B')

    def test_price_and_status_are_inventory_manager_only(self):
        with self.assertRaises(AccessError):
            self.unit.with_user(self.salesperson).write({'sale_price': 2_000_000})
        with self.assertRaises(AccessError):
            self.unit.with_user(self.salesperson).write({'unit_status': 'sold'})
        self.unit.with_user(self.inventory_manager).write({
            'sale_price': 2_000_000, 'unit_status': 'sold'})
        self.assertEqual(self.unit.sale_price, 2_000_000)

    def test_only_inventory_manager_deletes_units(self):
        with self.assertRaises(AccessError):
            self.unit.with_user(self.salesperson).unlink()
        doomed = self.env['broker.unit'].create({
            'name': 'U-del', 'unit_purpose': 'to_sale', 'sale_price': 1,
            'seller_sales_person': self.salesperson.id})
        doomed.with_user(self.inventory_manager).unlink()
        self.assertFalse(doomed.exists())

    # ---------------------------------------------------------------- counters

    def test_counter_follows_unit_write_access(self):
        counter = self.env['broker.unit.counter'].with_user(self.salesperson).create({
            'unit_id': self.unit.id, 'counter_type': 'electricity', 'serial_no': 'E-1'})
        self.assertEqual(counter.with_user(self.plain).serial_no, 'E-1', "counters readable by all")
        with self.assertRaises(AccessError):
            self.env['broker.unit.counter'].with_user(self.salesperson2).create({
                'unit_id': self.unit.id, 'counter_type': 'gas'})
        counter.with_user(self.salesperson).unlink()

    # ---------------------------------------------------------------- master data

    def test_projects_read_only_for_users_crud_for_manager(self):
        project = self.env['developer.project'].with_user(self.inventory_manager).create({
            'name': 'P-1', 'developer_id': self.env['res.partner'].sudo().create(
                {'name': 'Dev Co', 'is_developer': True}).id})
        self.assertEqual(project.with_user(self.plain).name, 'P-1')
        with self.assertRaises(AccessError):
            self.env['developer.project'].with_user(self.salesperson).create({
                'name': 'nope', 'developer_id': project.developer_id.id})
        with self.assertRaises(AccessError):
            project.with_user(self.salesperson).write({'name': 'nope'})
        project.with_user(self.inventory_manager).write({'active': False})
        self.assertFalse(project.active, "archive is the daily-use path, and the manager can")

    def test_cities_admin_only(self):
        with self.assertRaises(AccessError):
            self.env['res.country.city'].with_user(self.inventory_manager).create({'name': 'nope'})
        admin = self.env['res.users'].create({
            'name': 'broker_admin_u', 'login': 'broker_admin_u',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('isky_20_broker_base.group_broker_admin').id])]})
        city = self.env['res.country.city'].with_user(admin).create({'name': 'Cairo East'})
        self.assertTrue(city)
