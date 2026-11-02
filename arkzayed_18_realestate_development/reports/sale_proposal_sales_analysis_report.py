from odoo import models, api


class SalesAnalysisReportHandler(models.AbstractModel):
    _name = 'report.arkzayed_18_realestate_development.sales_analysis_pdf'
    _description = 'Sales Analysis PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env['sale.proposal.sales.analysis.wizard'].browse(docids[0]) if docids else None

        residential_data = {
            'monthly': [],
            'by_type': [],
            'total_units': 0,
            'total_price': 0,
        }

        business_data = {
            'monthly': [],
            'by_type': [],
            'total_units': 0,
            'total_price': 0,
        }

        contract_details = []

        if wizard and wizard.exists():
            try:
                aggregated = wizard._aggregate_data()
                residential_data = aggregated.get('residential', residential_data)
                business_data = aggregated.get('business', business_data)
                contract_details = aggregated.get('contract_details', [])
            except Exception as e:
                print(f"Error aggregating data: {e}")

        return {
            'doc_ids': docids,
            'doc_model': 'sale.proposal.sales.analysis.wizard',
            'docs': self.env['sale.proposal.sales.analysis.wizard'].browse(docids),
            'residential_data': residential_data,
            'business_data': business_data,
            'contract_details': contract_details,
        }