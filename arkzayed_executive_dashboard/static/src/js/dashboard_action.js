/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

function fmtMoney(value) {
    return Math.round(value || 0).toLocaleString("en-US");
}

function fmtPct(value) {
    return (value || 0).toFixed(1) + "%";
}

function toIso(d) {
    return d.toISOString().slice(0, 10);
}

function presetRange(preset) {
    const today = new Date();
    const y = today.getFullYear();
    const m = today.getMonth();
    if (preset === "all_time") {
        return { date_from: "", date_to: "" };
    }
    if (preset === "last_month") {
        return { date_from: toIso(new Date(y, m - 1, 1)), date_to: toIso(new Date(y, m, 0)) };
    }
    if (preset === "this_year") {
        return { date_from: toIso(new Date(y, 0, 1)), date_to: toIso(today) };
    }
    // this_month (default)
    return { date_from: toIso(new Date(y, m, 1)), date_to: toIso(today) };
}

export class ExecutiveDashboard extends Component {
    static template = "arkzayed_executive_dashboard.ExecutiveDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.donutRef = useRef("donutCanvas");
        this.trendRef = useRef("trendCanvas");
        this.collDonutRef = useRef("collDonutCanvas");
        this.collTimelineRef = useRef("collTimelineCanvas");
        this.cashFlowRef = useRef("cashFlowCanvas");
        this.ageingRef = useRef("ageingCanvas");
        this.forecastRef = useRef("forecastCanvas");
        this.ageingChart = null;
        this.forecastChart = null;
        this.chequeDonutRef = useRef("chequeDonutCanvas");
        this.donutChart = null;
        this.trendChart = null;
        this.collDonutChart = null;
        this.collTimelineChart = null;
        this.cashFlowChart = null;
        this.chequeDonutChart = null;

        this.state = useState({
            loading: true,
            projects: [],
            projectId: false,
            data: null,
            areaMode: "built",
            byTypeData: null,
            byTypeLoading: true,
            collapsedTypes: {},
            byTypePreset: "all_time",
            byTypeDateFrom: "",
            byTypeDateTo: "",
            collData: null,
            collLoading: true,
            collPreset: "this_month",
            collDateFrom: "",
            collDateTo: "",
            cashData: null,
            recvData: null,
            pipeData: null,
        });

        this.fmtMoney = fmtMoney;
        this.fmtPct = fmtPct;

        onWillStart(async () => {
            await this.loadData();
        });

        onMounted(() => {
            this.renderCharts();
        });

        onWillUnmount(() => {
            this.donutChart?.destroy();
            this.trendChart?.destroy();
            this.collDonutChart?.destroy();
            this.collTimelineChart?.destroy();
            this.cashFlowChart?.destroy();
            this.chequeDonutChart?.destroy();
            this.ageingChart?.destroy();
            this.forecastChart?.destroy();
        });
    }

    async loadData() {
        this.state.loading = true;
        await Promise.all([
            this.loadSales(), this.loadByType(), this.loadCollections(), this.loadCash(),
            this.loadReceivables(), this.loadPipeline(),
        ]);
        this.state.loading = false;
    }

    async loadReceivables() {
        this.state.recvData = await this.orm.call(
            "arkzayed.executive.dashboard", "get_receivables", [], { project_id: this.state.projectId || false }
        );
        setTimeout(() => this.renderCharts(), 0);
    }

    async loadPipeline() {
        this.state.pipeData = await this.orm.call(
            "arkzayed.executive.dashboard", "get_pipeline", [], { project_id: this.state.projectId || false }
        );
    }

    async loadCash() {
        this.state.cashData = await this.orm.call(
            "arkzayed.executive.dashboard", "get_cash_position", []
        );
        setTimeout(() => this.renderCharts(), 0);
    }

    async loadSales() {
        this.state.data = await this.orm.call(
            "arkzayed.executive.dashboard", "get_sales_inventory",
            [], { project_id: this.state.projectId || false, area_mode: this.state.areaMode }
        );
        setTimeout(() => this.renderCharts(), 0);
    }

    async onAreaModeChange(ev) {
        this.state.areaMode = ev.target.checked ? "villas_landed" : "built";
        await Promise.all([this.loadSales(), this.loadByType()]);
    }

    async loadByType() {
        this.state.byTypeLoading = true;
        const range = this.state.byTypePreset === "custom"
            ? { date_from: this.state.byTypeDateFrom, date_to: this.state.byTypeDateTo }
            : presetRange(this.state.byTypePreset);
        this.state.byTypeData = await this.orm.call(
            "arkzayed.executive.dashboard", "get_sales_by_type", [], {
                project_id: this.state.projectId || false,
                date_from: range.date_from || false,
                date_to: range.date_to || false,
                area_mode: this.state.areaMode,
            }
        );
        this.state.byTypeLoading = false;
    }

    openDrill(drill) {
        if (!drill) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: drill.name,
            res_model: drill.model,
            domain: drill.domain || [],
            res_id: drill.res_id || false,
            views: drill.res_id ? [[false, "form"]] : [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    // click on a chart segment/bar opens the matching list
    drillOptions(rows) {
        return {
            onClick: (_ev, elements) => {
                if (elements.length) {
                    this.openDrill(rows[elements[0].index]?.drill);
                }
            },
            onHover: (ev, elements) => {
                const target = ev.native?.target;
                if (target) {
                    target.style.cursor = elements.length ? "pointer" : "default";
                }
            },
        };
    }

    toggleType(type) {
        this.state.collapsedTypes[type] = !this.state.collapsedTypes[type];
    }

    async onByTypePresetChange(preset) {
        this.state.byTypePreset = preset;
        if (preset !== "custom") {
            this.state.byTypeDateFrom = "";
            this.state.byTypeDateTo = "";
        }
        await this.loadByType();
    }

    async onByTypeCustomDateChange(which, ev) {
        this.state.byTypePreset = "custom";
        if (which === "from") {
            this.state.byTypeDateFrom = ev.target.value;
        } else {
            this.state.byTypeDateTo = ev.target.value;
        }
        if (this.state.byTypeDateFrom && this.state.byTypeDateTo) {
            await this.loadByType();
        }
    }

    async loadCollections() {
        this.state.collLoading = true;
        const range = this.state.collPreset === "custom"
            ? { date_from: this.state.collDateFrom, date_to: this.state.collDateTo }
            : presetRange(this.state.collPreset);
        this.state.collData = await this.orm.call(
            "arkzayed.executive.dashboard", "get_collections_vs_due",
            [], {
                project_id: this.state.projectId || false,
                date_from: range.date_from || false,
                date_to: range.date_to || false,
            }
        );
        this.state.collDateFrom = this.state.collData.date_from;
        this.state.collDateTo = this.state.collData.date_to;
        this.state.collLoading = false;
        setTimeout(() => this.renderCharts(), 0);
    }

    async onCollPresetChange(preset) {
        this.state.collPreset = preset;
        await this.loadCollections();
    }

    async onCollCustomDateChange(which, ev) {
        this.state.collPreset = "custom";
        if (which === "from") {
            this.state.collDateFrom = ev.target.value;
        } else {
            this.state.collDateTo = ev.target.value;
        }
        if (this.state.collDateFrom && this.state.collDateTo) {
            await this.loadCollections();
        }
    }

    renderCharts() {
        if (!window.Chart) {
            return;
        }
        if (this.state.data) {
            this.renderDonut();
            this.renderTrend();
        }
        if (this.state.collData) {
            this.renderCollDonut();
            this.renderCollTimeline();
        }
        if (this.state.recvData) {
            this.renderAgeing();
        }
        if (this.state.cashData) {
            this.renderForecast();
            this.renderCashFlow();
            this.renderChequeDonut();
        }
    }

    renderDonut() {
        const canvas = this.donutRef.el;
        if (!canvas) {
            return;
        }
        const rows = this.state.data.inventory_split.filter((r) => r.value > 0);
        const drillOpts = this.drillOptions(rows);
        this.donutChart?.destroy();
        this.donutChart = new window.Chart(canvas.getContext("2d"), {
            type: "doughnut",
            data: {
                labels: rows.map((r) => r.label),
                datasets: [{
                    data: rows.map((r) => r.value),
                    backgroundColor: rows.map((r) => r.color),
                    borderWidth: 2,
                    borderColor: "#ffffff",
                }],
            },
            options: {
                ...drillOpts,
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 12 } } },
                },
                cutout: "62%",
            },
        });
    }

    renderTrend() {
        const canvas = this.trendRef.el;
        if (!canvas) {
            return;
        }
        const trend = this.state.data.trend;
        this.trendChart?.destroy();
        this.trendChart = new window.Chart(canvas.getContext("2d"), {
            type: "bar",
            data: {
                labels: trend.map((r) => r.label),
                datasets: [{
                    label: "Sales Value",
                    data: trend.map((r) => r.value),
                    backgroundColor: "#0f2a4a",
                    borderRadius: 4,
                }],
            },
            options: {
                ...this.drillOptions(trend),
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: {
                        ticks: {
                            callback: (v) => fmtMoney(v),
                        },
                    },
                },
            },
        });
    }

    renderAgeing() {
        const canvas = this.ageingRef.el;
        if (!canvas) {
            return;
        }
        const rows = this.state.recvData.ageing.filter((r) => r.amount > 0);
        const drillOpts = this.drillOptions(rows);
        this.ageingChart?.destroy();
        this.ageingChart = new window.Chart(canvas.getContext("2d"), {
            type: "doughnut",
            data: {
                labels: rows.map((r) => r.label),
                datasets: [{
                    data: rows.map((r) => r.amount),
                    backgroundColor: rows.map((r) => r.color),
                    borderWidth: 2,
                    borderColor: "#ffffff",
                }],
            },
            options: {
                ...drillOpts,
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 12 } } } },
                cutout: "62%",
            },
        });
    }

    renderForecast() {
        const canvas = this.forecastRef.el;
        if (!canvas) {
            return;
        }
        // the last bucket ("Later") spans years of post-dated cheques and would flatten the rest
        const rows = this.state.cashData.forecast.slice(0, -1);
        this.forecastChart?.destroy();
        this.forecastChart = new window.Chart(canvas.getContext("2d"), {
            type: "bar",
            data: {
                labels: rows.map((r) => r.label),
                datasets: [
                    { label: "In hand", data: rows.map((r) => r.hand), backgroundColor: "#0f2a4a", borderRadius: 4 },
                    { label: "At Hermes", data: rows.map((r) => r.hermes), backgroundColor: "#8b5cf6", borderRadius: 4 },
                ],
            },
            options: {
                ...this.drillOptions(rows),
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 12 } } } },
                scales: { x: { stacked: true }, y: { stacked: true, ticks: { callback: (v) => fmtMoney(v) } } },
            },
        });
    }

    renderCollDonut() {
        const canvas = this.collDonutRef.el;
        if (!canvas) {
            return;
        }
        const rows = this.state.collData.status_split.filter((r) => r.value > 0);
        const drillOpts = this.drillOptions(rows);
        this.collDonutChart?.destroy();
        this.collDonutChart = new window.Chart(canvas.getContext("2d"), {
            type: "doughnut",
            data: {
                labels: rows.map((r) => r.label),
                datasets: [{
                    data: rows.map((r) => r.value),
                    backgroundColor: rows.map((r) => r.color),
                    borderWidth: 2,
                    borderColor: "#ffffff",
                }],
            },
            options: {
                ...drillOpts,
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 12 } } },
                },
                cutout: "62%",
            },
        });
    }

    renderCollTimeline() {
        const canvas = this.collTimelineRef.el;
        if (!canvas) {
            return;
        }
        const timeline = this.state.collData.timeline;
        this.collTimelineChart?.destroy();
        this.collTimelineChart = new window.Chart(canvas.getContext("2d"), {
            type: "bar",
            data: {
                labels: timeline.map((r) => r.label),
                datasets: [{
                    label: "Collected",
                    data: timeline.map((r) => r.amount),
                    backgroundColor: "#0d9488",
                    borderRadius: 4,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: {
                        ticks: {
                            callback: (v) => fmtMoney(v),
                        },
                    },
                },
            },
        });
    }

    renderCashFlow() {
        const canvas = this.cashFlowRef.el;
        if (!canvas) {
            return;
        }
        const rows = this.state.cashData.flow_rows;
        this.cashFlowChart?.destroy();
        this.cashFlowChart = new window.Chart(canvas.getContext("2d"), {
            type: "bar",
            data: {
                labels: rows.map((r) => r.label),
                datasets: [
                    { label: "In", data: rows.map((r) => r.in), backgroundColor: "#059669", borderRadius: 4 },
                    { label: "Out", data: rows.map((r) => r.out), backgroundColor: "#dc2626", borderRadius: 4 },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 12 } } } },
                scales: {
                    y: {
                        ticks: {
                            callback: (v) => fmtMoney(v),
                        },
                    },
                },
            },
        });
    }

    renderChequeDonut() {
        const canvas = this.chequeDonutRef.el;
        if (!canvas) {
            return;
        }
        const rows = this.state.cashData.cheque_status_split;
        const drillOpts = this.drillOptions(rows);
        this.chequeDonutChart?.destroy();
        this.chequeDonutChart = new window.Chart(canvas.getContext("2d"), {
            type: "doughnut",
            data: {
                labels: rows.map((r) => r.label),
                datasets: [{
                    data: rows.map((r) => r.value),
                    backgroundColor: rows.map((r) => r.color),
                    borderWidth: 2,
                    borderColor: "#ffffff",
                }],
            },
            options: {
                ...drillOpts,
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 12 } } },
                },
                cutout: "62%",
            },
        });
    }
}

registry.category("actions").add("arkzayed_executive_dashboard", ExecutiveDashboard);
