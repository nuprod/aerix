/** @odoo-module **/
import { registry } from "@web/core/registry";
import { uuid } from "@web/core/utils/uuid";

const printZPLService = {
  dependencies: ["bus_service"],

  start(env, { bus_service }) {
    let clientId = window.sessionStorage.getItem("client_id");
    if (!clientId) {
      clientId = uuid();
      window.sessionStorage.setItem("client_id", clientId);
    }
    console.log("Client ID:", clientId);

    try {
      bus_service.addChannel("nuprod_print_browser");
      bus_service.subscribe("nuprod_print_browser", (payload) => {
        console.log(payload.client_id, clientId);
        if (payload.client_id === clientId) {
          BrowserPrint.getLocalDevices(
            function (device_list) {
              let devices = [];

              if (Array.isArray(device_list)) {
                devices = device_list;
              } else if (device_list && device_list.printer) {
                devices = device_list.printer;
              } else if (device_list && typeof device_list === "object") {
                for (let key in device_list) {
                  if (Array.isArray(device_list[key])) {
                    devices = devices.concat(device_list[key]);
                  }
                }
              }

              console.log("Devices found:", devices);

              if (!Array.isArray(devices) || devices.length === 0) {
                console.error("No printers found");
                return;
              }

              const targetDevice = devices.find((d) => {
                const connectionMatch = d.connection.match(
                  /(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/,
                );
                const deviceIP = connectionMatch ? connectionMatch[1] : null;

                return (
                  d.connection === payload.ip_address ||
                  d.connection.includes(payload.ip_address) ||
                  deviceIP === payload.ip_address ||
                  d.name.includes(payload.ip_address) ||
                  d.uid === payload.ip_address
                );
              });

              if (!targetDevice) {
                console.error(payload.ip_address);
                console.log(
                  "Available connections:",
                  devices.map((d) => d.connection),
                );
                return;
              }

              targetDevice.send(
                payload.render,
                function (success) {
                  console.log("Print successful!");
                },
                function (error) {
                  console.error("Print error:", error);
                },
              );
            },
            function (error) {
              console.error("Failed to get devices:", error);
            },
            "printer",
          );
        }
      });
    } catch (e) {
      console.error("Subscribe error:", e);
    }
    return { clientId };
  },
};

registry.category("services").add("print_zpl_browser", printZPLService);
