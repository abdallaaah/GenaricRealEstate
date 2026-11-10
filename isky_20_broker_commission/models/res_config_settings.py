from odoo import api, fields, models

from .commission_feature_codes import (
    COMMISSION_FEATURE_HIERARCHY_STACKING,
    COMMISSION_FEATURE_OPERATIONS_SHARE,
    COMMISSION_FEATURE_PROJECT_ADDITIONAL,
    COMMISSION_FEATURE_REFERRAL_PLAN_MATCHING,
    COMMISSION_FEATURE_REQUIRE_PLAN_ASSIGNMENT,
    COMMISSION_FEATURE_RETROACTIVE,
    COMMISSION_FEATURE_SEGMENTATION,
    COMMISSION_FEATURE_TEAM_ROLLUP,
)

# (flag code, settings field, label shown on the flag record)
COMMISSION_FLAG_FIELDS = [
    (COMMISSION_FEATURE_SEGMENTATION, 'commission_segmentation_enabled', "Commission: Segmented Plans"),
    (COMMISSION_FEATURE_RETROACTIVE, 'commission_retroactive_enabled', "Commission: Retroactive Effect"),
    (COMMISSION_FEATURE_TEAM_ROLLUP, 'commission_team_rollup_enabled', "Commission: Team Target Rollup"),
    (COMMISSION_FEATURE_HIERARCHY_STACKING, 'commission_hierarchy_stacking_enabled',
     "Commission: Hierarchy Stacking"),
    (COMMISSION_FEATURE_PROJECT_ADDITIONAL, 'commission_project_additional_enabled',
     "Commission: Project Additional Percentage"),
    (COMMISSION_FEATURE_OPERATIONS_SHARE, 'commission_operations_share_enabled',
     "Commission: Operations Share"),
    (COMMISSION_FEATURE_REQUIRE_PLAN_ASSIGNMENT, 'commission_require_plan_assignment_enabled',
     "Commission: Require Plan Assignment"),
    (COMMISSION_FEATURE_REFERRAL_PLAN_MATCHING, 'commission_referral_plan_matching_enabled',
     "Commission: Referral Plan Matching"),
]


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    base_percentage_threshold = fields.Float(
        config_parameter='isky_20_broker_commission.base_percentage_threshold',
        help="Below this project base commission percentage, the computed commission is halved.")
    base_max_commission_percentage_amount = fields.Float(
        config_parameter='isky_20_broker_commission.base_max_commission_percentage_amount',
        help="When the project base commission percentage exactly equals the threshold, "
             "the computed commission is capped at this amount.")
    double_commission_mode = fields.Selection([
        ('multiply', "Double the commission"),
        ('add_base_segment', "Add the plan's entry-band rate"),
    ], config_parameter='isky_20_broker_commission.double_commission_mode', default='multiply',
        help="How a project marked Double Commission is treated. The pre-v20 engine added the "
             "entry band's rate; the v20 rewrite doubled the amount instead. They give different "
             "numbers, so the reading a client's plans were written against is a setting.")

    commission_trigger_stage = fields.Selection([
        ('confirmed_contract', "Confirmed Contract"),
        ('collected', "Collected"),
    ], config_parameter='isky_20_broker_commission.commission_trigger_stage',
        default='confirmed_contract',
        help="The deal stage that creates commission. The first version of this engine used "
             "Confirmed Contract; the live later version moved off it, on the grounds that a "
             "signed contract is not money received.")
    achieve_commission_basis = fields.Selection([
        ('flat', "Flat amount"),
        ('per_million', "Rate per million of contract price"),
    ], config_parameter='isky_20_broker_commission.achieve_commission_basis', default='flat',
        help="How an achieve plan's Commission Amount is read for hierarchy beneficiaries. "
             "Both pre-v20 generations and the live production engine read it as a rate per "
             "million (1000 earns 0.1%); this module currently reads it as a flat amount, a 12x "
             "difference on a 12M deal. The default preserves this module's behaviour -- switch "
             "to per-million if the plans were written against the older engine.")

    # A company field rather than a config parameter: which company receives commission is
    # a property of the company that owns the deal, and differs per company in a group.
    commission_broker_company_id = fields.Many2one(
        related='company_id.commission_broker_company_id', readonly=False,
        help="Book commission earned on this company's deals into this company instead. For a "
             "group where a developer company sells and a separate broker company pays the sales "
             "team. Empty means commission stays with the company that owns the deal.")

    # Feature flags live on broker.feature.flag (per company, and visible in one list for
    # portal and commission alike); these booleans are just the Settings surface for them.
    commission_segmentation_enabled = fields.Boolean(
        string="Segmented Commission Plans", compute='_compute_commission_feature_flags',
        inverse='_inverse_commission_segmentation',
        help="Allow a plan to compute from its own from-to segments instead of Odoo's "
             "target brackets.")
    commission_retroactive_enabled = fields.Boolean(
        string="Retroactive Effect", compute='_compute_commission_feature_flags',
        inverse='_inverse_commission_retroactive',
        help="When a deal lifts someone into a higher segment, re-rate the deals already "
             "booked in that period and record the difference as an adjustment.")
    commission_team_rollup_enabled = fields.Boolean(
        string="Team Target Rollup", compute='_compute_commission_feature_flags',
        inverse='_inverse_commission_team_rollup',
        help="Count the deals of everyone reporting to a person towards that person's target.")
    commission_hierarchy_stacking_enabled = fields.Boolean(
        string="Hierarchy Stacking", compute='_compute_commission_feature_flags',
        inverse='_inverse_commission_hierarchy_stacking',
        help="A manager who closes a deal personally also earns the achieve-type commission "
             "of every level below their own.")
    commission_project_additional_enabled = fields.Boolean(
        string="Project Additional Percentage", compute='_compute_commission_feature_flags',
        inverse='_inverse_commission_project_additional',
        help="Apply project.commission's Additional Percentage as an uplift on the computed "
             "commission. Captured in the UI since the first version of this engine but never "
             "read, so it stays off until a client confirms the intended behaviour.")

    commission_operations_share_enabled = fields.Boolean(
        string="Operations Share", compute='_compute_commission_feature_flags',
        inverse='_inverse_commission_operations_share',
        help="Also pay Operations staff who are on an approved achieve plan. They sit outside "
             "the sales reporting chain, so they never arrive through a deal's commission "
             "hierarchy; the live production engine pays them alongside it.")
    commission_require_plan_assignment_enabled = fields.Boolean(
        string="Require Plan Assignment", compute='_compute_commission_feature_flags',
        inverse='_inverse_commission_require_plan_assignment',
        help="Only pay someone from a plan they are actually assigned to on the deal's date, "
             "per the plan's own From/To lines. Off by default: switching it on can stop paying "
             "people whose assignment rows were never filled in.")

    commission_referral_plan_matching_enabled = fields.Boolean(
        string="Referral Plan Matching", compute='_compute_commission_feature_flags',
        inverse='_inverse_commission_referral_plan_matching',
        help="Pick plans by how the deal was referred: a plan flagged With Broker applies only "
             "to broker-referred deals, and an unflagged plan only to deals with no broker. "
             "Matching is exact, so enabling this needs a plan per referral combination.")

    @api.depends_context('company')
    def _compute_commission_feature_flags(self):
        FeatureFlag = self.env['broker.feature.flag']
        for settings in self:
            for code, field_name, _label in COMMISSION_FLAG_FIELDS:
                settings[field_name] = FeatureFlag.is_feature_enabled(code, default=False)

    def _set_commission_flag(self, code):
        field_name, label = next(
            (field_name, label) for flag_code, field_name, label in COMMISSION_FLAG_FIELDS
            if flag_code == code)
        self.env['broker.feature.flag']._set_flag(
            code, label, self[field_name], category='commission')

    def _inverse_commission_segmentation(self):
        self._set_commission_flag(COMMISSION_FEATURE_SEGMENTATION)

    def _inverse_commission_retroactive(self):
        self._set_commission_flag(COMMISSION_FEATURE_RETROACTIVE)

    def _inverse_commission_team_rollup(self):
        self._set_commission_flag(COMMISSION_FEATURE_TEAM_ROLLUP)

    def _inverse_commission_hierarchy_stacking(self):
        self._set_commission_flag(COMMISSION_FEATURE_HIERARCHY_STACKING)

    def _inverse_commission_project_additional(self):
        self._set_commission_flag(COMMISSION_FEATURE_PROJECT_ADDITIONAL)

    def _inverse_commission_operations_share(self):
        self._set_commission_flag(COMMISSION_FEATURE_OPERATIONS_SHARE)

    def _inverse_commission_require_plan_assignment(self):
        self._set_commission_flag(COMMISSION_FEATURE_REQUIRE_PLAN_ASSIGNMENT)

    def _inverse_commission_referral_plan_matching(self):
        self._set_commission_flag(COMMISSION_FEATURE_REFERRAL_PLAN_MATCHING)
