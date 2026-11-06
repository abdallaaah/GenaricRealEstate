from odoo import models, fields, api


class PersonCommission(models.Model):
    """Commission model for Opportunity, EOI, Reservation, and Sale Proposal"""
    _name = "realestate.commission"
    _description = "Realestate Commission Line"

    opportunity_id = fields.Many2one('crm.lead', string='Opportunity', ondelete='cascade')
    eoi_id = fields.Many2one('eoi.eoi', string='EOI', ondelete='cascade')
    sale_reservation_id = fields.Many2one('real.estate.sale.reservation', string='Reservation', ondelete='cascade')
    sale_proposal_id = fields.Many2one('sale.proposal', string='Sale Proposal', ondelete='cascade')

    employee_id = fields.Many2one('res.users', string='Employee', required=True)

    # Phase 4 (D2): the role. The four old hierarchy builders wrote a hardcoded position name
    # into jop_position and never consulted job.level at all. job_level_id is now the role,
    # and jop_position is kept and filled from it so legacy views and reports that read the
    # Char keep working. It also still carries the team-position fallback for a participant
    # with no job level, so incomplete configuration never drops someone silently.
    job_level_id = fields.Many2one('job.level', string='Job Level')
    jop_position = fields.Char(string='Job Position')

    commission = fields.Float(string='Commission %', default=100)

    # Phase 4 (D1): carried over from commission.commission (L2), which this model replaces.
    # That model defaulted commission to 1 while this one defaults to 100; 100 wins, matching
    # the three documents that actually drive payment.
    job_level_related_id = fields.Many2one(
        'job.level', related='employee_id.job_level_id', string="Employee's Job Level",
        readonly=True)
    is_tcr_sales_person = fields.Boolean(
        string='Is Sales Person', compute='_compute_is_sales_person', store=True)

    @api.depends('employee_id', 'opportunity_id', 'opportunity_id.user_id',
                 'opportunity_id.sales_ids')
    def _compute_is_sales_person(self):
        """Whether this person is the salesperson on the opportunity. Moved verbatim in
        behaviour from commission.commission."""
        for rec in self:
            is_sales = False
            if rec.opportunity_id and rec.employee_id:
                if rec.opportunity_id.user_id and rec.opportunity_id.user_id == rec.employee_id:
                    is_sales = True
                elif rec.opportunity_id.sales_ids and rec.employee_id in rec.opportunity_id.sales_ids:
                    is_sales = True
            rec.is_tcr_sales_person = is_sales
