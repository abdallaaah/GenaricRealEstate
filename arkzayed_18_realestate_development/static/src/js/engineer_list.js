/** @odoo-module **/
import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { download } from "@web/core/network/download";

export class EngineerInventoryListController extends ListController {
    async onExportExcel() {
        const kind = (this.props.context || {}).engineer_kind || "residential";
        await download({
            url: "/ark_engineer_menu/export",
            data: { kind, domain: JSON.stringify(this.model.root.domain || []) },
        });
    }
}

registry.category("views").add("ark_engineer_inventory_list", {
    ...listView,
    Controller: EngineerInventoryListController,
    buttonTemplate: "arkzayed_18_realestate_development.EngineerListView.Buttons",
});
