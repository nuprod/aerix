/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { MrpDisplayRecord } from "@mrp_workorder/mrp_display/mrp_display_record";
import { uuid } from "@web/core/utils/uuid";

patch(MrpDisplayRecord.prototype, {
	setup() {
		super.setup();
	},

	get displayPrintButton() {
		return false;
	},

	async onClickSendPrintingJob() {
		let sessionStorage = window.sessionStorage;
		let clientId = sessionStorage.getItem("client_id");
		if (!clientId) {
			sessionStorage.setItem("client_id", uuid());
			clientId = sessionStorage.getItem("client_id");
		}
		await this.model.orm.call("mrp.production", "send_print_render", [
			[this.props.production.data.id],
			this.record.mrp_report_name,
			clientId,
		]);
	},

	async onClickCloseProduction() {
		await this.onClickSendPrintingJob();
		await super.onClickCloseProduction();
	},
});
