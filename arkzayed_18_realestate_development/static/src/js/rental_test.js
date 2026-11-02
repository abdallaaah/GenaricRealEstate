/** @odoo-module **/
//const ApexCharts = window.ApexCharts;

import { useService } from '@web/core/utils/hooks';
import { registry } from "@web/core/registry";
import { Component, useState, mount, useEffect } from "@odoo/owl";

class UnitDashboard extends Component {
    setup() {
        this.orm = useService('orm');
        this.actionService = useService('action');
        this.state = useState({
            avail_unit: 0,
            reserved_unit: 0,
            lease_unit: 0,
            blocked_unit: 0,
            sold_unit: 0,
            total_unit: 0,

            sale_sold: 0,
            sold_total: 0,

            rent_total: 0,
            draft_contract: 0,
            running_contract: 0,
            expire_contract: 0,
            pending_invoice: 0,
        });

        this.loadUnitStats();
    }

    async loadUnitStats() {
        const result = await this.orm.call('real.estate.unit', 'get_unit_stats');
        this.state.avail_unit = result.avail_unit;
        this.state.reserved_unit = result.reserved_unit;
        this.state.lease_unit = result.lease_unit;
        this.state.blocked_unit = result.blocked_unit;
        this.state.sold_unit = result.sold_unit;
        this.state.total_unit = result.total_unit;

        this.state.sold_total = result.sold_total;
        this.state.sale_sold = result.sale_sold;
        this.state.sale_reserved = result.sale_reserved;

//        this.state.rent_total = result.rent_total;
//        this.state.draft_contract = result.draft_contract;
//        this.state.running_contract = result.running_contract;
//        this.state.expire_contract = result.expire_contract;
//        this.state.pending_invoice = result.pending_invoice;
        this.unitType(result.unit_type);
        this.unitStages(result.unit_stage);
//        this.topBrokers(result.tenancy_top_broker);
//        this.topBrokersSold(result.tenancy_top_broker);
//        this.tenancyDuePaid(result.due_paid_amount);
//        this.soldDuePaid(result.due_paid_amount);
    }

    view_action(ev, name, res_model, domain = []) {
        ev.preventDefault();
        this.actionService.doAction({
            name: this.env._t(name),
            type: 'ir.actions.act_window',
            res_model: res_model,
            domain: domain,
            views: [[false, 'kanban'], [false, 'list'], [false, 'form']],
            target: 'current'
        });
    }

    unitType(data) {
        const options = {
            series: data[1],
            chart: {
                type: 'donut',
                height: 410
            },
            colors: ['#33679c', '#6FFCD0', '#F084A3', '#82CDFF'],
            dataLabels: {
                enabled: false
            },
            labels: data[0],
            legend: {
                position: 'bottom',
            },
        };
        this.renderGraph("#unit_type", options);
    }

    unitStages(data) {
        console.log(data);
        const options = {
            series: data[1],
            chart: {
                type: 'pie',
                height: 410
            },
            colors: ['#FFADAD', '#FFD6A5', '#FDFFB6', '#CAFFBF', '9BF6FF'],
            dataLabels: {
                enabled: false
            },
            labels: data[0],
            legend: {
                position: 'bottom',
            },
        };
        this.renderGraph("#unit_stage", options);
    }

    topBrokers(data) {
        const options = {
            series: [{
                name: "Tenancies",
                data: data[1],
            }],
            chart: {
                height: 350,
                type: 'bar',
            },
            colors: ['#FFADAD', '#FFD6A5', '#FDFFB6', '#CAFFBF', '9BF6FF'],
            plotOptions: {
                bar: {
                    columnWidth: '45%',
                    distributed: true,
                }
            },
            dataLabels: {
                enabled: false
            },
            legend: {
                show: false
            },
            xaxis: {
                categories: data[0],
                labels: {
                    style: {
                        fontSize: '12px'
                    }
                }
            }
        };
        this.renderGraph("#top_brokers", options);
    }

    topBrokersSold(data) {
        const options = {
            series: [{
                name: "Property Sale",
                data: data[3],
            }],
            chart: {
                height: 350,
                type: 'bar',
            },
            colors: ['#FFADAD', '#FFD6A5', '#FDFFB6', '#CAFFBF', '9BF6FF'],
            plotOptions: {
                bar: {
                    columnWidth: '45%',
                    distributed: true,
                }
            },
            dataLabels: {
                enabled: false
            },
            legend: {
                show: false
            },
            xaxis: {
                categories: data[2],
                labels: {
                    style: {
                        fontSize: '12px'
                    }
                }
            }
        };
        this.renderGraph("#top_brokers_sale", options);
    }

    tenancyDuePaid(data) {
        const options = {
            series: data[3],
            chart: {
                type: 'pie',
                height: 410
            },
            colors: ['#FF6464', '#96BB7C'],
            dataLabels: {
                enabled: false
            },
            labels: data[2],
            legend: {
                position: 'bottom',
            },
        };
        this.renderGraph("#tenancy_due_paid", options);
    }

    soldDuePaid(data) {
        const options = {
            series: data[1],
            chart: {
                type: 'pie',
                height: 410
            },
            colors: ['#FF1700', '#4AA96C'],
            dataLabels: {
                enabled: false
            },
            labels: data[0],
            legend: {
                position: 'bottom',
            },
        };
        this.renderGraph("#sold_due_paid", options);
    }

    renderGraph(render_id, options) {
        const graphContainer = document.querySelector(render_id);
        graphContainer.innerHTML = '';
        const graphData = new ApexCharts(graphContainer, options);
        graphData.render();
    }

    static template = 'rentalDashboard';
}

registry.category("actions").add("unit_dashboard", UnitDashboard);

export default UnitDashboard;
