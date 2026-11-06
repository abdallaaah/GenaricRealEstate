from odoo import models


class SalesCommissionHooks(models.AbstractModel):
    """No-op bases for the commission-hierarchy builders that live in L3.

    Phase 2 moved the live `_build_commission_hierarchy` / `compute_person_hierarchy`
    implementations into isky_18_realestate_developer_commission (L3) but left their callers
    in L2 - 10 call sites for the first, 2 for the second. Because these are plain runtime
    attribute reads rather than `@api.depends` paths, no install gate caught it: creating a
    reservation, a contract or an EOI in an L2-only database raised AttributeError. Found by
    the Phase 3 step 5 tests.

    These no-ops make L2 self-sufficient. L3 declares the same methods on the same models and
    is loaded after L2, so when the commission module is installed its real implementations
    override these.
    """
    _name = 'realestate.sales.commission.hooks'
    _description = 'Optional L3 Commission Hooks'

    def _build_commission_hierarchy(self):
        """Base: no commission module, so there is no hierarchy to build."""
        return False

    def compute_person_hierarchy(self):
        """Base: no commission module, so there is no person hierarchy to compute."""
        return False

    def _commission_lines_for_copy(self):
        """Commission lines to carry onto a document created from this one, as One2many
        commands. Base: none, because commission lines live in L3."""
        return []

    def _copy_commission_to_contract(self, contract):
        """Copy this document's commission lines onto a contract. Base: nothing to copy.

        Phase 4: crm_lead used to call env['realestate.commission'].create() directly from L2,
        which raises KeyError when the commission module is absent - the same cross-layer
        break step 5 found for the hierarchy builders."""
        return False
