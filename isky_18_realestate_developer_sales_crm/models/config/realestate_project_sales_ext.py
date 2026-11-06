from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RealestateProject(models.Model):
    """Phase 3 step 5: the per-project installments override.

    These fields are sales concepts, so they are added here as an _inherit rather than on the
    L0 model itself - L0 (unit_inventory) must not know about sales."""
    _inherit = 'realestate.project'

    installments_mode = fields.Selection(
        [('inherit', 'Company Default'), ('on', 'On'), ('off', 'Off')],
        string='Installments',
        default='inherit',
        help="Whether deals in this project generate installment lines. 'Company Default' "
             "follows the Use Installments setting in Sales Setup.")

    installments_effective = fields.Boolean(
        string='Installments Active',
        compute='_compute_installments_effective',
        help="The resolved value: the company default when the mode is 'Company Default', "
             "otherwise the explicit override.")

    @api.depends('installments_mode', 'company_id',
                 'company_id.installments_enabled')
    def _compute_installments_effective(self):
        for project in self:
            if project.installments_mode == 'on':
                project.installments_effective = True
            elif project.installments_mode == 'off':
                project.installments_effective = False
            else:
                company = project.company_id or self.env.company
                project.installments_effective = company.installments_enabled

    def _has_installment_lines(self):
        """Whether any installment or maintenance installment line belongs to this project.

        Neither installment.lines nor sale.proposal carries project_id, so the project is
        reached three ways: through the reservation (which has project_id), through the line's
        stored unit_id, and through sale_proposal_id.unit_id.project_id. A line counts if any
        route matches. R3's constrains on the line models guarantees at least one route exists.
        """
        self.ensure_one()
        if not self.id:
            return False
        # R3: three routes, not two. `unit_id` on a line is computed only from
        # sale_proposal_id.unit_id, so it is empty for a reservation-only line; and walking
        # sale_proposal_id.unit_id.project_id directly also catches a line whose stored unit_id
        # has not been recomputed. Any one match counts.
        domain = [
            '|', '|', ('reservation_id.project_id', '=', self.id),
                      ('unit_id.project_id', '=', self.id),
                      ('sale_proposal_id.unit_id.project_id', '=', self.id),
        ]
        return bool(
            self.env['installment.lines'].sudo().search_count(domain)
            or self.env['maintenance.installment.lines'].sudo().search_count(domain)
        )

    def write(self, vals):
        """Lock rule (NEEDS REVIEW, see decisions log): the override cannot be changed once
        the project has installment lines.

        Implemented in write() rather than as @api.constrains deliberately: constrains fires
        on every write that includes the field, even when the value is unchanged, which would
        make the project form unsaveable as soon as any installment line existed. Comparing
        old against new means only a real change is rejected.
        """
        if 'installments_mode' in vals:
            for project in self:
                if project.installments_mode == vals['installments_mode']:
                    continue
                if project._has_installment_lines():
                    raise ValidationError(_(
                        "Installments cannot be switched for project '%(project)s': it "
                        "already has installment lines.\n\n"
                        "Change this setting before any installments are generated, or "
                        "remove the existing lines first.",
                        project=project.name,
                    ))
        return super().write(vals)
