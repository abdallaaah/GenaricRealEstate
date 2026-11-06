from odoo import _, models


class SalesInstallmentsGate(models.AbstractModel):
    """Phase 3 step 5: resolves whether a deal may generate installment lines.

    An abstract mixin rather than a method copied onto both models - reservation and contract
    resolve their project differently but share the decision. Deliberately NOT added to
    L0's `installment.mixin`: the flags it reads (realestate.project.installments_mode,
    res.company.installments_enabled) are declared in this L2 module, and L0 must not know
    about sales. `real.estate.unit` also inherits `installment.mixin`, so putting this there
    would push a sales dependency into L0.
    """
    _name = 'realestate.sales.installments.gate'
    _description = 'Installments Toggle Gate'

    def _deal_project(self):
        """The project this deal belongs to. Overridden per model, because a reservation has
        project_id while a contract has to be resolved through its unit or its reservation.

        Deliberately neutral in name: Phase 4's commission basis asks the same question, and
        one resolver with two consumers beats two resolvers that can drift apart."""
        self.ensure_one()
        return self.env['realestate.project']

    def _installments_project(self):
        """The project whose installments setting governs this deal."""
        self.ensure_one()
        return self._deal_project()

    def _installments_allowed(self):
        """True when this deal may generate installment lines.

        Falls back to the company default when no project can be resolved, so a deal with no
        project behaves exactly as it did before this toggle existed."""
        self.ensure_one()
        project = self._installments_project()
        if project:
            return project.installments_effective
        company = self.company_id or self.env.company
        return company.installments_enabled

    def _installments_off_notification(self):
        """What a calculate button returns when installments are off: a warning, never an
        exception. Step 5 requires the deal to still complete."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Installments are off'),
                'message': _(
                    "No installment lines were generated: installments are turned off for "
                    "this deal's project. Change it on the project, or in Settings > Real "
                    "Estate Sales > Sales Setup."),
                'type': 'warning',
                'sticky': False,
            },
        }
