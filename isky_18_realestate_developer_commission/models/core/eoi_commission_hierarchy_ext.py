from odoo import fields, models


class EOICommission(models.Model):
    """EOI side of the commission hierarchy.

    realestate.commission is this module's own model (L3) - the eoi.eoi model lives in L2 and must
    not depend on it, so the field and the engine hook live here.

    Phase 4: the hand-written hierarchy builder that used to be in this file is gone. All four
    documents now share realestate.commission.hierarchy.engine; see the decisions log,
    2026-11-06 (D2, D3) for what changed and why.
    """
    # _name is required alongside a list _inherit when extending an existing model:
    # without it Odoo treats the class as a new anonymous model and the inherited
    # Many2many relations collide on their table names.
    _name = 'eoi.eoi'
    _inherit = ['eoi.eoi', 'realestate.commission.hierarchy.engine']

    _commission_fk = 'eoi_id'

    commission_ids = fields.One2many(
        'realestate.commission',
        'eoi_id',
        string='Commission'
    )

    # Explicit entry points: see _commission_build() for why these cannot be left to the MRO.
    def _build_commission_hierarchy(self):
        return self._commission_build()

    def compute_person_hierarchy(self):
        return self._commission_build()
