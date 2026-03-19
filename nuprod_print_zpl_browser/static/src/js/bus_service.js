/** @odoo-module **/
import { registry } from "@web/core/registry";

const printZPLService = {
  dependencies: ["bus_service"],

  start(env, { bus_service }) {
    let clientId = window.sessionStorage.getItem("client_id");
    if (!clientId) {
      clientId = crypto.randomUUID();
      window.sessionStorage.setItem("client_id", clientId);
    }
    console.log("Client ID:", clientId);

    try {
      bus_service.addChannel("nuprod_print_browser");
      bus_service.subscribe("nuprod_print_browser", (payload) => {
        console.log(payload.client_id, clientId);
        console.log("Received print request:", payload);
        if (payload.client_id === clientId || payload.client_id === "BROADCAST") {
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
              console.log("Available connections:", devices.map((d) => ({
                name: d.name,
                connection: d.connection,
                uid: d.uid
              })));
              const targetDevice = devices.find((d) => {
                const uidIP = d.uid ? d.uid.split(":")[0] : null;
                // const connectionMatch = d.connection.match(
                //   /(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/,
                // );
                console.log(uidIP, payload.ip_address);
                // const deviceIP = connectionMatch ? connectionMatch[1] : null;

                return (
                  d.connection === payload.ip_address ||
                  d.connection.includes(payload.ip_address) ||
                  uidIP === payload.ip_address ||
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

              console.log("Target device found:", targetDevice);

              if (payload.is_pdf) {
                const binaryStr = atob(payload.render);
                const bytes = new Uint8Array(binaryStr.length);
                for (let i = 0; i < binaryStr.length; i++) {
                  bytes[i] = binaryStr.charCodeAt(i);
                }
                const blob = new Blob([bytes], { type: "application/pdf" });
                targetDevice.sendFile(
                  blob,
                  function (success) {
                    console.log("Print successful!");
                  },
                  function (error) {
                    console.error("Print error:", error);
                  },
                );
              } else {
                targetDevice.send(
                  payload.render,
                  function (success) {
                    console.log("Print successful!");
                  },
                  function (error) {
                    console.error("Print error:", error);
                  },
                );
              }
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
