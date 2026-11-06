from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHierarchy(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project_type = cls.env['realestate.project.type'].create({'project_type': 'residential'})

    def _project(self, abbreviation, **vals):
        vals.setdefault('name', abbreviation)
        vals.setdefault('abbreviation', abbreviation)
        vals.setdefault('project_type_ids', [(6, 0, [self.project_type.id])])
        return self.env['realestate.project'].create(vals)

    def _cluster(self, abbreviation, parent, **vals):
        vals.setdefault('name', abbreviation)
        vals.setdefault('abbreviation', abbreviation)
        vals.setdefault('project_type_ids', [(6, 0, [self.project_type.id])])
        vals.setdefault('parent_source_id', '%s,%d' % (parent._name, parent.id))
        return self.env['cluster'].create(vals)

    def _zone(self, abbreviation, parent, **vals):
        vals.setdefault('name', abbreviation)
        vals.setdefault('abbreviation', abbreviation)
        vals.setdefault('project_type_ids', [(6, 0, [self.project_type.id])])
        if parent._name == 'realestate.project':
            vals.setdefault('parent_id', parent.id)
        else:
            vals.setdefault('parent_source_id', '%s,%d' % (parent._name, parent.id))
        return self.env['zone'].create(vals)

    def _unit(self, abbreviation, parent, **vals):
        vals.setdefault('abbreviation', abbreviation)
        vals.setdefault('name', abbreviation)
        vals.setdefault('parent_source_id', '%s,%d' % (parent._name, parent.id))
        return self.env['real.estate.unit'].create(vals)

    def test_two_level_system_code(self):
        """Project with 2 levels (project -> unit) generates correct system codes."""
        project = self._project('P1')
        unit = self._unit('U01', project)
        self.assertEqual(unit.system_code, 'P1-U01')

    def test_cluster_zone_system_code_no_code_change(self):
        """Project with cluster and zone generates correct codes with no code change needed
        in the engine - the same chain-walk handles any depth."""
        project = self._project('P2')
        template = self.env['realestate.hierarchy.template'].create({
            'name': 'Cluster+Zone',
            'level_ids': [
                (0, 0, {'level_type': 'cluster', 'sequence': 10}),
                (0, 0, {'level_type': 'zone', 'sequence': 20}),
            ],
        })
        project.hierarchy_template_id = template.id

        cluster = self._cluster('C1', project)
        zone = self._zone('Z1', cluster)
        unit = self._unit('U01', zone)

        self.assertEqual(cluster.system_code, 'P2-C1')
        self.assertEqual(zone.system_code, 'P2-C1-Z1')
        self.assertEqual(unit.system_code, 'P2-C1-Z1-U01')

    def test_duplicate_code_under_same_parent_rejected(self):
        """Duplicate code under the same parent is rejected."""
        project = self._project('P3')
        self._cluster('C1', project)
        with self.assertRaises(ValidationError):
            self._cluster('C1', project)

    def test_level_definition_locks_after_first_unit(self):
        """Changing levels after the first unit is rejected at server level; adding new
        nodes afterward is still allowed; existing node codes never change."""
        project = self._project('P4')
        template = self.env['realestate.hierarchy.template'].create({
            'name': 'Zone only',
            'level_ids': [(0, 0, {'level_type': 'zone', 'sequence': 10})],
        })
        project.hierarchy_template_id = template.id

        zone = self._zone('Z1', project)
        self._unit('U01', zone)
        self.assertTrue(project.hierarchy_locked)

        # Changing the project's template once it has units is rejected.
        other_template = self.env['realestate.hierarchy.template'].create({'name': 'Other'})
        with self.assertRaises(ValidationError):
            project.hierarchy_template_id = other_template.id

        # Adding a level to the (now locked) template is rejected.
        with self.assertRaises(ValidationError):
            self.env['realestate.hierarchy.level'].create({
                'template_id': template.id, 'level_type': 'cluster', 'sequence': 5,
            })

        # Removing the existing level from the locked template is rejected.
        with self.assertRaises(ValidationError):
            template.level_ids.unlink()

        # Existing node codes never change once locked.
        with self.assertRaises(ValidationError):
            zone.abbreviation = 'ZZ'

        # But adding new nodes under the existing (locked) structure is still allowed.
        zone2 = self._zone('Z2', project)
        unit2 = self._unit('U02', zone2)
        self.assertEqual(unit2.system_code, 'P4-Z2-U02')
