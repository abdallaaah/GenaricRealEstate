from odoo import Command, api, fields, models


class CommissionHierarchyEngine(models.AbstractModel):
    """The one commission-hierarchy engine (Phase 4, D2 and D3).

    Replaces four divergent implementations - lead (was in L2), EOI, reservation and contract -
    which disagreed on the role set, on what happens to a salesperson with no team, and on
    whether the result was a stored compute or an imperative action. The audit of those
    differences is in the decisions log, 2026-11-06.

    Two rules shape the design:

    * **Team traversal decides WHO participates. `job.level` decides WHAT they are.** The four
      old copies hardcoded `['Sales Person', 'Sales Manager', 'Sales Sector Manager',
      'Director']` and assigned a role by where a `crm.team` field sat in that list, writing a
      Char. The plan requires roles assigned by role, not by name, so the role now comes from
      `user.job_level_id` and the ordering from `job.level.sequence`.
    * **Convergent behaviour (D3).** All four documents now behave the way reservation and
      contract did: a user with no team is still a participant as the team-position fallback,
      and all four team roles are considered. The EOI copy used to clear every line when the
      salesperson had no team, which silently dropped their commission; the lead copy omitted
      Sales Sector Manager entirely.
    """
    _name = 'realestate.commission.hierarchy.engine'
    _description = 'Commission Hierarchy Engine'

    # Concrete models override: the FK on realestate.commission pointing back at them.
    _commission_fk = False

    # The team field -> fallback label used only when a participant has no job level, so that
    # nobody drops out of the hierarchy just because configuration is incomplete. These are
    # labels of last resort, never the source of role identity.
    _TEAM_ROLE_FALLBACKS = (
        ('__self__', 'Sales Person'),
        ('sales_manager_id', 'Sales Manager'),
        ('operation_id', 'Sales Sector Manager'),
        ('director_id', 'Director'),
    )

    DEFAULT_COMMISSION = 100.0

    def _commission_participants(self):
        """[(user, fallback_label)] for this document, in hierarchy order.

        Starts from the document's salesperson and walks their team; when the deal is split,
        every user in `sales_ids` contributes their own team chain too.
        """
        self.ensure_one()
        users = []

        def _chain(user):
            if not user:
                return []
            member = self.env['crm.team.member'].search([('user_id', '=', user.id)], limit=1)
            team = member.crm_team_id if member else self.env['crm.team']
            out = [(user, 'Sales Person')]
            if team:
                for field_name, label in self._TEAM_ROLE_FALLBACKS:
                    if field_name == '__self__':
                        continue
                    out.append((team[field_name], label))
            return out

        users.extend(_chain(self._commission_salesperson()))
        if self._commission_is_split():
            for person in self._commission_split_users():
                users.extend(_chain(person))
        return [(u, label) for u, label in users if u]

    # -- per-document hooks, overridden where the field names differ --------------------
    def _commission_salesperson(self):
        self.ensure_one()
        return self.user_id

    def _commission_is_split(self):
        self.ensure_one()
        return bool(self.split_deal)

    def _commission_split_users(self):
        self.ensure_one()
        return self.sales_ids

    def _commission_is_eligible(self):
        """Whether this document should carry commission lines at all. Overridden by the lead,
        which only does so for opportunities, and by documents gated on the commission basis."""
        self.ensure_one()
        return True

    def _commission_basis_allows(self, this_basis):
        """True when the governing project's effective basis is `this_basis`.

        The plan requires commission to be calculated only on the selected basis document, with
        no double calculation, so the reservation and the contract each ask this with their own
        value. Lead and EOI do not: Phase 3 fixes them as informational only, and the
        "same manager mapping across lead, EOI, reservation and contract" acceptance criterion
        requires them to keep building a hierarchy regardless of basis.

        With no project resolvable, falls back to the company default rather than blocking, so a
        deal with no project behaves as it did before the basis existed.
        """
        self.ensure_one()
        project = self._deal_project()
        if project:
            return project.commission_basis_effective == this_basis
        company = self.company_id or self.env.company
        return company.commission_basis == this_basis

    # -- the engine --------------------------------------------------------------------
    def _commission_lines(self):
        """The commission lines this document should have, as create commands."""
        self.ensure_one()
        if not self._commission_is_eligible():
            return [Command.clear()]

        # one entry per user, keeping the most senior role they hold (lowest sequence),
        # which preserves the old "lowest list index wins" behaviour
        chosen = {}
        for user, fallback in self._commission_participants():
            level = user.job_level_id
            seq = level.sequence if level else 10
            current = chosen.get(user.id)
            if current is None or seq < current['sequence']:
                chosen[user.id] = {
                    'sequence': seq,
                    'level': level,
                    'label': level.name or fallback,
                    'role_key': level._role_key() if level else fallback,
                }

        # a role's percentage is shared between everyone holding it, as before
        role_counts = {}
        for data in chosen.values():
            role_counts[data['role_key']] = role_counts.get(data['role_key'], 0) + 1

        ordered = sorted(chosen.items(), key=lambda kv: (kv[1]['sequence'], kv[0]))
        return [Command.clear()] + [
            Command.create({
                'employee_id': user_id,
                'job_level_id': data['level'].id if data['level'] else False,
                'jop_position': data['label'],
                'commission': self.DEFAULT_COMMISSION / role_counts[data['role_key']],
            })
            for user_id, data in ordered
        ]

    def _commission_build(self):
        """Build and store this document's commission lines.

        Deliberately NOT named `_build_commission_hierarchy`. L2's
        `realestate.sales.commission.hooks` declares no-op methods under that name so that
        sales_crm works without this module, and when a document inherits both mixins the L2
        no-op wins the MRO - measured, not assumed: before this rename the engine never ran and
        every document silently produced zero lines. Each concrete model therefore overrides
        the public entry points and calls this, which is resolution by explicit override
        rather than by mixin ordering.
        """
        for rec in self:
            rec.commission_ids = rec._commission_lines()
        return True
