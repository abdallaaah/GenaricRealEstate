from odoo import Command, api, fields, models


class CrmLeadCommission(models.Model):
    """Lead side of the commission hierarchy (Phase 4, D1 and D2).

    The lead's commission used to live in L2 `sales_crm` against its own near-duplicate line
    model `commission.commission`, with a hand-written hierarchy builder that omitted Sales
    Sector Manager and defaulted the percentage to 1 instead of 100. All of that is replaced
    by the shared engine and the shared line model here.
    """
    # _name is required alongside a list _inherit when extending an existing model:
    # without it Odoo treats the class as a new anonymous model and the inherited
    # Many2many relations collide on their table names.
    _name = 'crm.lead'
    _inherit = ['crm.lead', 'realestate.commission.hierarchy.engine']

    _commission_fk = 'opportunity_id'

    commission_ids = fields.One2many(
        'realestate.commission', 'opportunity_id',
        compute='compute_person_hierarchy', store=True, readonly=False,
        string='Commission')

    @api.depends('user_id', 'sales_ids', 'split_deal')
    def compute_person_hierarchy(self):
        """Redeclared with @api.depends so the stored compute still recomputes - the engine's
        own entry point carries no depends, because the other three documents call it
        imperatively. Same guard pattern as S6."""
        return self._commission_build()

    def _build_commission_hierarchy(self):
        return self._commission_build()

    def _commission_is_eligible(self):
        """Only opportunities carry commission; a plain lead does not."""
        self.ensure_one()
        return self.type == 'opportunity'

    # -- the hooks L2 calls -------------------------------------------------------------
    def _commission_lines_for_copy(self):
        """Carry this opportunity's commission lines onto the reservation it creates."""
        self.ensure_one()
        return [
            Command.create({
                'employee_id': line.employee_id.id,
                'job_level_id': line.job_level_id.id,
                'jop_position': line.jop_position,
                'commission': line.commission,
            })
            for line in self.commission_ids
        ]

    def _copy_commission_to_contract(self, contract):
        """Copy this opportunity's commission lines onto a contract."""
        self.ensure_one()
        if not contract:
            return False
        self.env['realestate.commission'].create([
            {
                'sale_proposal_id': contract.id,
                'employee_id': line.employee_id.id,
                'job_level_id': line.job_level_id.id,
                'jop_position': line.jop_position,
                'commission': line.commission,
            }
            for line in self.commission_ids
        ])
        return True
