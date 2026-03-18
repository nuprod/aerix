/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ViewButton } from "@web/views/view_button/view_button";
import { onMounted } from "@odoo/owl";

patch(ViewButton.prototype, {
	setup() {
		super.setup();
		onMounted(() => {
			let sessionStorage = window.sessionStorage;
			let clientId = sessionStorage.getItem("client_id");
			if (!clientId) {
				sessionStorage.setItem("client_id", crypto.randomUUID());
				clientId = sessionStorage.getItem("client_id");
			}
			if ("record" in this.props && "context" in this.props.record) {
				this.props.record.context.client_id = clientId;
			} else if ("list" in this.props && "context" in this.props.list) {
				this.props.list.context.client_id = clientId;
			}
		});
	},
});
