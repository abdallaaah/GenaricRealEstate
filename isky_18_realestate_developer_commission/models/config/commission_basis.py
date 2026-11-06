from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

BASIS = [('reservation', 'Reservation'), ('contract', 'Contract')]


class ResCompany(models.Model):
    """Phase 4: the commission basis default. Company-level, so a multi-company database can
    run one company on reservations and another on contracts."""
    _inherit = 'res.company'

    commission_basis = fields.Selection(
        BASIS, string='Commission Basis', default='contract',
        help="Which document commission is calculated on. 'Contract' is the default because "
             "the plan fixes commission timing at signing. A project can override this.")

    def write(self, vals):
        """Lock rule: the default cannot change while a project that inherits it already has
        commission.

        In write() comparing old against new, not @api.constrains, for the reason step 5
        established: constrains fires on every write that includes the field, so saving the
        company form would be rejected outright once any such project existed."""
        if 'commission_basis' in vals:
            for company in self:
                if company.commission_basis == vals['commission_basis']:
                    continue
                projects = self.env['realestate.project'].search([
                    ('commission_basis_mode', '=', 'inherit'),
                    ('company_id', 'in', (company.id, False)),
                ])
                blocking = projects.filtered(lambda p: p._has_commission())
                if blocking:
                    raise ValidationError(_(
                        "Commission Basis cannot be changed for company '%(company)s': "
                        "%(count)d project(s) inheriting this default already have commission "
                        "(%(names)s).\n\n"
                        "Set those projects to an explicit basis first, or change the default "
                        "before any commission is calculated.",
                        company=company.name,
                        count=len(blocking),
                        names=', '.join(blocking.mapped('name')[:5])))
        return super().write(vals)


class RealestateProject(models.Model):
    """Phase 4: the per-project commission basis override.

    Added here as an _inherit rather than on the L0 model: commission is an L3 concept and L0
    must not know about it. Same arrangement as the installments override in L2."""
    _inherit = 'realestate.project'

    commission_basis_mode = fields.Selection(
        [('inherit', 'Company Default')] + BASIS,
        string='Commission Basis', default='inherit',
        help="Which document commission is calculated on for deals in this project.")

    commission_basis_effective = fields.Selection(
        BASIS, string='Effective Commission Basis',
        compute='_compute_commission_basis_effective',
        help="The resolved basis: the company default when the mode is 'Company Default', "
             "otherwise the explicit override.")

    @api.depends('commission_basis_mode', 'company_id', 'company_id.commission_basis')
    def _compute_commission_basis_effective(self):
        for project in self:
            if project.commission_basis_mode in ('reservation', 'contract'):
                project.commission_basis_effective = project.commission_basis_mode
            else:
                company = project.company_id or self.env.company
                project.commission_basis_effective = company.commission_basis

    def _has_commission(self):
        """Whether any commission line exists for a deal in this project.

        The plan requires the basis to lock once commission is 'calculated or posted, even if
        the deal is cancelled', so this counts lines regardless of document state - no state
        filter, deliberately.

        realestate.commission carries no project_id, so the project is reached through each
        document, mirroring the two-route search step 5 needed for installment lines: a
        reservation has project_id, while a contract resolves only through its unit.
        """
        self.ensure_one()
        if not self.id:
            return False
        return bool(self.env['realestate.commission'].sudo().search_count([
            '|', '|', '|',
            ('sale_reservation_id.project_id', '=', self.id),
            ('sale_proposal_id.unit_id.project_id', '=', self.id),
            ('sale_reservation_id.unit_id.project_id', '=', self.id),
            ('opportunity_id.unit_id.project_id', '=', self.id),
        ]))

    def write(self, vals):
        """Lock rule, same shape and same reasoning as the company default above."""
        if 'commission_basis_mode' in vals:
            for project in self:
                if project.commission_basis_mode == vals['commission_basis_mode']:
                    continue
                if project._has_commission():
                    raise ValidationError(_(
                        "Commission Basis cannot be changed for project '%(project)s': it "
                        "already has commission.\n\n"
                        "The basis locks once commission is calculated, even if the deal was "
                        "cancelled.",
                        project=project.name))
        return super().write(vals)
