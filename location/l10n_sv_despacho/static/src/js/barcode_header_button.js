/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { StockBarcodeKanbanRenderer } from "@stock_barcode/kanban/stock_barcode_kanban_renderer";

patch(StockBarcodeKanbanRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
    },

    async onDownloadLoadingRoutesReport() {
        try {
            const action = await this.orm.call(
                "dispatch.route",
                "action_download_loading_routes_report",
                []
            );

            if (action) {
                await this.actionService.doAction(action);
            }
        } catch (error) {
            this.notification.add(
                "No se pudo generar el reporte de rutas en carga.",
                { type: "danger" }
            );
            throw error;
        }
    },
});