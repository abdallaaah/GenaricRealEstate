from collections import OrderedDict

from odoo import api, fields, models

APPENDIX_MAX_LINES = 150


class ReportCostDistribution(models.AbstractModel):
    _name = 'report.arkzayed_cost_distribution.report_cost_distribution'
    _description = 'Cost Distribution Executive Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['arkzayed.cost.distribution'].browse(docids).sorted(
            key=lambda d: (d.create_date or fields.Datetime.now(), d.id))
        allocations = docs.mapped('allocation_ids')
        total = sum(docs.mapped('amount'))
        direct = sum(docs.filtered(lambda d: d.cost_type == 'direct').mapped('amount'))
        indirect = total - direct

        buildings = OrderedDict()
        for alloc in allocations.sorted(key=lambda a: (a.building_id.system_code or '~', a.unit_id.system_code or '')):
            key = alloc.building_id.id or 0
            row = buildings.setdefault(key, {
                'name': alloc.building_id.system_code or alloc.building_id.display_name or 'No building',
                'units': set(), 'area': 0.0, 'amount': 0.0,
            })
            row['units'].add(alloc.unit_id.id)
            row['area'] += alloc.unit_area
            row['amount'] += alloc.amount
        building_rows = []
        for row in buildings.values():
            row['unit_count'] = len(row['units'])
            row['share'] = row['amount'] / total * 100 if total else 0.0
            building_rows.append(row)

        dates = [d for d in docs.mapped('create_date') if d]
        company = docs[:1].move_id.company_id or self.env.company
        return {
            'doc_ids': docs.ids,
            'doc_model': 'arkzayed.cost.distribution',
            'docs': docs,
            'company': company,
            'currency': docs[:1].currency_id or company.currency_id,
            'user_name': self.env.user.name,
            'today': fields.Date.context_today(self),
            'date_from': min(dates).date() if dates else False,
            'date_to': max(dates).date() if dates else False,
            'total_amount': total,
            'direct_amount': direct,
            'indirect_amount': indirect,
            'distribution_count': len(docs),
            'unit_count': len(set(allocations.mapped('unit_id').ids)),
            'building_count': len([r for r in building_rows if r['name'] != 'No building']),
            'building_rows': building_rows,
            'allocations': allocations.sorted(
                key=lambda a: (a.distribution_id.name or '', a.building_id.system_code or '', a.unit_id.system_code or '')),
            'show_appendix': 0 < len(allocations) <= APPENDIX_MAX_LINES,
            'appendix_limit': APPENDIX_MAX_LINES,
        }
