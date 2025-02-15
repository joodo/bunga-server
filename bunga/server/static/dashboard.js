$.fn.serializeObject = function () {
  var o = {};
  var a = this.serializeArray();
  $.each(a, function () {
    if (o[this.name]) {
      if (!o[this.name].push) {
        o[this.name] = [o[this.name]];
      }
      o[this.name].push(this.value || "");
    } else {
      o[this.name] = this.value || "";
    }
  });
  return o;
};

$(document).ready(function () {
  $(".bunga-form")
    .toArray()
    .forEach((form) => {
      form.loadData = (data) => {
        form.querySelectorAll("input").forEach((input) => {
          if (input.name in data) {
            if (input.type === "checkbox") {
              input.checked = data[input.name];
              input.insertAdjacentHTML(
                "beforebegin",
                `<input type="hidden" name=${input.name} value="false">`
              );
            } else {
              input.value = data[input.name];
            }
          }
        });
      };
      form.showResult = async (response) => {
        if (response.ok) {
          showAlert("保存成功", "success");
        } else {
          const data = await response.json();

          if ("detail" in data) {
            showAlert(data["detail"], "danger");
          }

          [...form.elements].forEach((field) => {
            if (field.setCustomValidity) {
              field.setCustomValidity("");
            }
          });

          for (let [fieldName, errorMessage] of Object.entries(data)) {
            const field = form.querySelector(`[name="${fieldName}"]`);
            if (field) {
              field.setCustomValidity(errorMessage);
              field.reportValidity();
            }
          }
        }
      };
      form.submitFunc = async () => {
        const data = getFormJson(form);
        const response = await fetch(form.action, {
          method: form.attributes["method"].value.toUpperCase(),
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": data["csrfmiddlewaretoken"],
            mode: "same-origin",
          },
          body: JSON.stringify(data),
        });
        await form.showResult(response);
        return response;
      };
      form.onsubmit = (e) => {
        e.preventDefault();
        form.submitFunc().then(form.afterSubmit);
      };
      form.execSubmit = () => {
        clearAlert();
        form.dispatchEvent(new Event("submit", { cancelable: true }));
      };

      if (!form.hasAttribute("bunga-createonly")) {
        fetch(form.action)
          .then(async (response) => {
            if (response.ok) {
              const data = await response.json();
              form.loadData(data);
            }
            return response;
          })
          .then(form.afterInit);
      }
    });
});

window.clearAlert = function () {
  document.querySelectorAll(".alert").forEach((alert) => alert.remove());
};

window.showAlert = function (message, alerttype) {
  clearAlert();
  $("#alert-placeholder").append(
    '<div class="alert alert-dismissible alert-' +
      alerttype +
      '">' +
      message +
      '<button class="btn-close" data-bs-dismiss="alert"></button></div>'
  );
};

function getFormJson(form) {
  const formData = new FormData(form);
  const formObject = {};
  formData.forEach((value, key) => {
    formObject[key] = value;
  });
  return formObject;
}
