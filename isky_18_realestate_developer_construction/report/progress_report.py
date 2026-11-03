from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models

STALE_DAYS = 14
GAP_ALERT = 15  # points of difference between a building's own progress and its units' average
DETAIL_LIMIT = 15
BANDS = [
    ('Not started', 0, 0, '#9ca3af'),
    ('1 - 25%', 0.01, 25, '#f59e0b'),
    ('26 - 50%', 25.01, 50, '#eab308'),
    ('51 - 75%', 50.01, 75, '#84cc16'),
    ('76 - 99%', 75.01, 99.99, '#22c55e'),
    ('Completed', 100, 100, '#059669'),
]


class ReportConstructionProgress(models.AbstractModel):
    _name = 'report.arkzayed_18_realestate_development.report_progress'
    _description = 'Construction Progress Executive Report'

    @api.model
    def _get_units(self, data):
        domain = []
        if data.get('project_id'):
            domain.append(('project_id', '=', data['project_id']))
        if data.get('building_ids'):
            domain.append(('building_id', 'in', data['building_ids']))
        return self.env['real.estate.unit'].search(domain)

    @staticmethod
    def _weighted(units):
        area = sum(u.unit_area or 0.0 for u in units)
        if area:
            return sum(u.construction_progress * (u.unit_area or 0.0) for u in units) / area
        return sum(u.construction_progress for u in units) / len(units) if units else 0.0

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        today = fields.Date.context_today(self)
        stale_before = today - timedelta(days=STALE_DAYS)
        units = self._get_units(data)

        def is_stale(u):
            return 0 < u.construction_progress < 100 and bool(u.progress_date) and u.progress_date < stale_before

        total_area = sum(units.mapped('unit_area'))
        overall = self._weighted(units)
        completed = units.filtered(lambda u: u.construction_progress >= 100)
        not_started = units.filtered(lambda u: u.construction_progress <= 0)
        in_progress = units - completed - not_started
        never_updated = units.filtered(lambda u: not u.progress_date)
        updated_recent = units.filtered(lambda u: u.progress_date and u.progress_date >= stale_before)
        stale = units.filtered(is_stale)

        bands = []
        for label, lo, hi, color in BANDS:
            sel = units.filtered(lambda u: lo <= u.construction_progress <= hi)
            bands.append({
                'label': label, 'color': color, 'count': len(sel), 'area': sum(sel.mapped('unit_area')),
                'share': len(sel) / len(units) * 100 if units else 0.0,
            })

        # --- by building ---
        groups = defaultdict(lambda: self.env['real.estate.unit'])
        for u in units:
            groups[u.building_id.id or 0] |= u
        building_rows = []
        for bid, bunits in groups.items():
            building = bunits[0].building_id
            avg = self._weighted(bunits)
            own = building.progress_percent if building and building.progress_date else None
            dates = [u.progress_date for u in bunits if u.progress_date]
            if building and building.progress_date:
                dates.append(building.progress_date)
            engineers = (building.responsible_engineer_id | bunits.mapped('responsible_engineer_id')) if building \
                else bunits.mapped('responsible_engineer_id')
            building_rows.append({
                'name': building.system_code or building.display_name if building else 'No building',
                'units': len(bunits), 'area': sum(bunits.mapped('unit_area')), 'avg': avg, 'own': own,
                'gap': (own - avg) if own is not None else None,
                'alert': own is not None and abs(own - avg) >= GAP_ALERT,
                'done': len(bunits.filtered(lambda u: u.construction_progress >= 100)),
                'last': max(dates) if dates else False,
                'stale': len(bunits.filtered(is_stale)),
                'engineer': ', '.join(engineers.mapped('name')) or '-',
            })
        building_rows.sort(key=lambda r: (r['avg'], r['name']))

        # --- by engineer ---
        eng = defaultdict(lambda: self.env['real.estate.unit'])
        for u in units:
            e = u.responsible_engineer_id or u.building_id.responsible_engineer_id
            eng[e.id or 0] |= u
        engineer_rows = []
        for eid, eunits in eng.items():
            dates = [u.progress_date for u in eunits if u.progress_date]
            engineer_rows.append({
                'name': self.env['res.users'].browse(eid).name if eid else 'No engineer assigned',
                'units': len(eunits), 'avg': self._weighted(eunits),
                'stale': len(eunits.filtered(is_stale)), 'last': max(dates) if dates else False,
            })
        engineer_rows.sort(key=lambda r: (r['name'] == 'No engineer assigned', -r['units']))

        # --- attention lists ---
        stale_sorted = sorted(stale, key=lambda u: u.progress_date)
        stale_rows = [{
            'unit': u.system_code, 'building': u.building_id.system_code or '-', 'progress': u.construction_progress,
            'last': u.progress_date, 'days': (today - u.progress_date).days,
            'engineer': (u.responsible_engineer_id or u.building_id.responsible_engineer_id).name or '-',
        } for u in stale_sorted[:DETAIL_LIMIT]]
        recent = self.env['arkzayed.construction.progress'].search(
            [('unit_id', 'in', units.ids)] if data.get('project_id') or data.get('building_ids') else [],
            order='date desc, id desc', limit=DETAIL_LIMIT)
        recent_rows = [{
            'date': r.date, 'target': r.target, 'percent': r.percent, 'note': r.note or '', 'user': r.user_id.name or '',
        } for r in recent]

        filters = []
        if data.get('project_id'):
            filters.append(self.env['realestate.project'].browse(data['project_id']).display_name)
        if data.get('building_ids'):
            filters.append(', '.join(self.env['real.estate.building'].browse(data['building_ids']).mapped('system_code')))

        return {
            'doc_ids': docids,
            'doc_model': 'arkzayed.progress.report.wizard',
            'docs': self.env['arkzayed.progress.report.wizard'].browse(docids),
            'company': self.env.company,
            'today': today,
            'user_name': self.env.user.name,
            'filters': ' | '.join(filters),
            'stale_days': STALE_DAYS,
            'gap_alert': GAP_ALERT,
            'overall': overall,
            'unit_count': len(units),
            'total_area': total_area,
            'completed': len(completed),
            'in_progress': len(in_progress),
            'not_started': len(not_started),
            'never_updated': len(never_updated),
            'updated_recent': len(updated_recent),
            'stale_count': len(stale),
            'bands': bands,
            'building_rows': building_rows,
            'alert_count': len([b for b in building_rows if b['alert']]),
            'engineer_rows': engineer_rows,
            'stale_rows': stale_rows,
            'stale_hidden': max(0, len(stale_sorted) - DETAIL_LIMIT),
            'recent_rows': recent_rows,
        }
