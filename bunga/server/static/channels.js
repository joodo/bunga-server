/*document.getElementById("update-chat-config-btn").onclick = function () {
  const form = document.getElementById("chat-config-form");
  form.submitFunc().then((success) => {
    if (success) {
      $("#channels-table").bootstrapTable("refresh");
    }
  });
};*/
document.getElementById("create-channel-btn").onclick = function () {
  const form = document.getElementById("channel-form");
  form.submitFunc().then((success) => {
    if (success) {
      form.reset();
      $("#channels-table").bootstrapTable("refresh");

      const modal = bootstrap.Modal.getInstance("#create-channel-model");
      modal.hide();
    }
  });
};

window.operateEvents = {
  "click .item-accounts": function (e, value, row, index) {
    window.location.assign(encodeURIComponent(row.group_id));
  },
  "click .item-rename": function (e, value, row, index) {
    const modalElement = $("#rename-model");
    modalElement.find("#channel-new-name").val(row.name);
    modalElement
      .find(".btn-confirm")
      .unbind()
      .click(async function () {
        const csrftoken = document.querySelector(
          "[name=csrfmiddlewaretoken]",
        ).value;
        await fetch(window.URLS["channel:rename"], {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrftoken,
            mode: "same-origin",
          },
          body: JSON.stringify({
            id: row.id,
            name: modalElement.find("#channel-new-name").val(),
          }),
        });

        const modal = bootstrap.Modal.getInstance("#rename-model");
        await modal.hide();
        $("#channels-table").bootstrapTable("refresh");
      });

    const modal = new bootstrap.Modal(modalElement);
    modal.show();
  },
  "click .item-dismiss": function (e, value, row, index) {
    const modalElement = $("#confirm-dismiss-model");
    modalElement
      .find("#dismissing-channel-info")
      .text(`[${row.id}] ${row.name}`);
    const url = `${window.URLS["channel:dismiss"]}?id=${encodeURIComponent(
      row.id,
    )}`;
    modalElement
      .find(".btn-confirm")
      .unbind()
      .click(async function () {
        await fetch(url);

        $("#channels-table").bootstrapTable("refresh");

        const modal = bootstrap.Modal.getInstance("#confirm-dismiss-model");
        await modal.hide();
      });

    const modal = new bootstrap.Modal(modalElement);
    modal.show();
  },
};

window.randomId = () => {
  document.getElementById("new-channel-id").value = Math.floor(
    Math.random() * 900000 + 100000,
  );
};
window.onCreateChannel = async (event) => {
  event.preventDefault();

  const form = event.target;
  const formData = new FormData(event.target);
  const formObject = {};
  formData.forEach((value, key) => {
    formObject[key] = value;
  });

  const csrftoken = document.querySelector("[name=csrfmiddlewaretoken]").value;
  const response = await fetch(form.action, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrftoken,
      mode: "same-origin",
    },
    body: JSON.stringify(formObject),
  });

  const data = await response.json();
  if (response.ok) {
    form.reset();
    $("#channels-table").bootstrapTable("refresh");

    const modal = bootstrap.Modal.getInstance("#create-channel-model");
    await modal.hide();
  } else {
    [...form.elements].forEach((field) => {
      if (field.setCustomValidity) {
        field.setCustomValidity("");
      }
    });

    for (let [fieldName, errorMessage] of Object.entries(data.errors)) {
      const field = form.querySelector(`[name="${fieldName}"]`);
      if (field) {
        field.setCustomValidity(errorMessage);
        field.reportValidity();
      }
    }
  }
};

window.showShareModal = function ({ download, api } = {}) {
  $("#download-page-address").val(new URL(download, document.baseURI).href);
  $("#api-address").val(new URL(api, document.baseURI).href);
  $("#share-model").modal("show");
};

import { copyToClipboard } from "./utils.js";

window.copyToClipboard = copyToClipboard;
