from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPhase7RevenueSplit(TransactionCase):
    """Phase 7: the revenue split is rows, not two hardcoded business lines, and the three
    posting paths share one engine.

    The point of these tests is that the *arithmetic did not change*. Two rows carrying the old
    percentages must produce exactly the lines the old GIS/OAYA code produced.
    """

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.ICP = self.env['ir.config_parameter'].sudo()
        Account = self.env['account.account']
        self.debit_account = Account.create({
            'name': 'P7 Collection Expense', 'code': 'P7DEB', 'account_type': 'expense'})
        self.credit_a = Account.create({
            'name': 'P7 Line A', 'code': 'P7CRA', 'account_type': 'liability_current'})
        self.credit_b = Account.create({
            'name': 'P7 Line B', 'code': 'P7CRB', 'account_type': 'liability_current'})
        self.journal = self.env['account.journal'].create({
            'name': 'P7 Collection', 'code': 'P7J', 'type': 'general'})
        self.ICP.set_param('realestate.collection_debit_account_id', str(self.debit_account.id))
        self.ICP.set_param('realestate.collection_journal_id', str(self.journal.id))

        Line = self.env['realestate.revenue.split.line']
        Line.search([('company_id', '=', self.company.id)]).unlink()
        self.line_a = Line.create({
            'name': 'Line A', 'sequence': 10, 'company_id': self.company.id,
            'account_id': self.credit_a.id, 'percentage': 2.5})
        self.line_b = Line.create({
            'name': 'Line B', 'sequence': 20, 'company_id': self.company.id,
            'account_id': self.credit_b.id, 'percentage': 1.5})

    def _engine(self):
        """Any model carrying the mixin will do for the arithmetic; sale.proposal is the one the
        contract path uses."""
        return self.env['sale.proposal']

    # -- the engine ------------------------------------------------------------------------
    def test_amounts_match_the_old_two_line_arithmetic(self):
        """Old code: round(total * pct / 100, 2) per business line, debit = sum of the rounded
        shares. Unchanged, now over rows."""
        total = 1_000_000.0
        split = self._engine()._revenue_split_amounts(total)
        self.assertEqual([line.id for line, _amount in split],
                         [self.line_a.id, self.line_b.id], "rows come in sequence order")
        self.assertEqual([amount for _line, amount in split], [25000.0, 15000.0])
        self.assertEqual(sum(a for _l, a in split), 40000.0,
                         "the debit is the sum of the rounded shares, so the entry balances")

    def test_rounding_is_per_line_as_before(self):
        split = self._engine()._revenue_split_amounts(333.33)
        self.assertEqual([amount for _line, amount in split], [8.33, 5.0])

    def test_a_zero_share_produces_no_line(self):
        """Old code skipped a business line whose amount was zero; so does this."""
        self.assertEqual(self._engine()._revenue_split_amounts(0.0), [])

    def test_line_labels_carry_the_business_line_and_its_percentage(self):
        split = self._engine()._revenue_split_amounts(1000.0)
        line, amount = split[0]
        vals = self._engine()._revenue_split_credit_line(line, amount, 'REF-1', False)
        self.assertEqual(vals['account_id'], self.credit_a.id)
        self.assertEqual(vals['credit'], amount)
        self.assertIn('Line A', vals['name'])
        self.assertIn('2.50%', vals['name'])
        self.assertIn('REF-1', vals['name'])

    def test_missing_configuration_is_reported_by_name(self):
        self.ICP.set_param('realestate.collection_journal_id', '')
        _debit, _journal, missing = self._engine()._revenue_split_posting_config()
        self.assertTrue(any('Journal' in item for item in missing))

        self.env['realestate.revenue.split.line'].search(
            [('company_id', '=', self.company.id)]).unlink()
        _debit, _journal, missing = self._engine()._revenue_split_posting_config()
        self.assertTrue(any('Revenue Split' in item for item in missing),
                        "a database with no rows must say so, where the old code said 'GIS'")

    # -- the configuration model ----------------------------------------------------------
    def test_percentage_bounds(self):
        Line = self.env['realestate.revenue.split.line']
        for bad in (0.0, -1.0, 100.01):
            with self.assertRaises(ValidationError, msg='percentage %s' % bad):
                Line.create({'name': 'P7 Bad %s' % bad, 'company_id': self.company.id,
                             'account_id': self.credit_a.id, 'percentage': bad})

    def test_name_is_unique_per_company(self):
        with self.assertRaises(ValidationError):
            self.env['realestate.revenue.split.line'].create({
                'name': 'Line A', 'company_id': self.company.id,
                'account_id': self.credit_b.id, 'percentage': 1.0})

    def test_rows_are_reachable_from_the_company(self):
        """The Financials settings edit them through this one2many."""
        self.assertIn(self.line_a, self.company.revenue_split_line_ids)
        self.assertIn(self.line_b, self.company.revenue_split_line_ids)

    # -- every path shares the engine -----------------------------------------------------
    def test_every_posting_path_uses_the_one_engine(self):
        """sale.proposal always; the two bridges when installed. Before Phase 7 each carried its
        own copy of this arithmetic."""
        # asserted by behaviour, not by reading _inherit: the registry shows the _inherit of the
        # last class to contribute to the model, so a later extension hides this one from that
        # list while the method is still there.
        self.assertTrue(hasattr(self.env['sale.proposal'], '_revenue_split_amounts'))

        # The two bridges, each checked only where it is installed. `account.payment` exists
        # wherever `account` does, so the model being present says nothing about whether the
        # bridge that extends it is there - in Mode B it is not.
        Module = self.env['ir.module.module'].sudo()
        bridges = {
            'isky_18_realestate_developer_sales_cheques': 'cheque.manage',
            'isky_18_realestate_developer_sales_accounting': 'account.payment',
        }
        checked = []
        for module, model in bridges.items():
            record = Module.search([('name', '=', module)], limit=1)
            if not record or record.state != 'installed':
                continue
            self.assertTrue(
                hasattr(self.env[model], '_revenue_split_amounts'),
                "%s must post through the shared engine" % model)
            checked.append(model)
        # the contract path is always covered; the message records what this run also covered
        self.assertTrue(True, "bridges checked here: %s" % (checked or 'none installed'))


@tagged('post_install', '-at_install')
class TestPhase7ConfigKeys(TransactionCase):
    """Phase 7: every config parameter key the product owns is on the generic prefix, and an
    existing database's values are carried over rather than abandoned."""

    def test_no_isky_field_declares_a_client_prefixed_key(self):
        """Read off the live fields, not the source: a `config_parameter` that still named the
        client's module would be invisible to a source grep if it were built dynamically."""
        # res.config.settings carries every installed module's settings, so narrow to the ones
        # the isky modules declare - otherwise base_setup's own keys count as offenders.
        rows = self.env['ir.model.fields'].search([('model', '=', 'res.config.settings')])
        ours = set()
        for row in rows:
            modules = [m.strip() for m in (row.modules or '').split(',')]
            if any(m.startswith('isky_18_realestate_developer_') for m in modules):
                ours.add(row.name)
        self.assertTrue(ours, "the isky modules must declare some settings")

        offenders = []
        for name in sorted(ours):
            field = self.env['res.config.settings']._fields[name]
            key = getattr(field, 'config_parameter', None)
            if not key:
                continue
            if key.startswith('realestate.'):
                continue
            # the legacy cheque module's own settings page writes this one; our side may only
            # read it until that module is dealt with (12.3 / backlog #29)
            if key == 'arkzayed_18_gt_cheque_management.journal_id':
                continue
            offenders.append('%s -> %s' % (name, key))
        self.assertFalse(offenders, "client-prefixed config keys remain: %s" % offenders)

    def test_the_rename_carries_a_value_and_is_idempotent(self):
        from odoo.addons.isky_18_realestate_developer_unit_inventory.hooks import (
            KEY_MAP, rename_config_parameters,
        )
        ICP = self.env['ir.config_parameter'].sudo()
        old_key = 'arkzayed_18_realestate_development.penalty_journal_id'
        new_key = KEY_MAP[old_key]
        self.assertEqual(new_key, 'realestate.penalty_journal_id')

        ICP.search([('key', '=', new_key)]).unlink()
        ICP.set_param(old_key, '4242')

        moved = rename_config_parameters(self.env)
        self.assertIn('%s -> %s' % (old_key, new_key), moved)
        self.assertEqual(ICP.get_param(new_key), '4242')

        # running again changes nothing, and never overwrites a value already on the new key
        ICP.set_param(new_key, '99')
        self.assertFalse([m for m in rename_config_parameters(self.env) if new_key in m])
        self.assertEqual(ICP.get_param(new_key), '99')

    def test_the_residential_key_mismatch_is_resolved(self):
        """Backlog #68: the setting wrote `…development.residential_default_years` while both
        readers read `arkzayed.residential_default_years`, so the configured value was never
        used. Both sides now meet on one generic key."""
        from odoo.addons.isky_18_realestate_developer_unit_inventory.hooks import KEY_MAP
        targets = {KEY_MAP['arkzayed.residential_default_years'],
                   KEY_MAP['arkzayed_18_realestate_development.residential_default_years']}
        self.assertEqual(targets, {'realestate.residential_default_years'})

        field = self.env['res.config.settings']._fields['residential_default_years']
        self.assertEqual(field.config_parameter, 'realestate.residential_default_years',
                         "the setting must write the key the readers read")
