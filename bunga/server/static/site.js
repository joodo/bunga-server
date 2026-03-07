$(document).ready(function () {
  // AList
  window.onRefreshClicked = fetchAListInfo;

  const aListForm = $("#alist-form")[0];
  aListForm.afterSubmit = async function (response) {
    if (response.ok) {
      fetchAListInfo();
    }
  };
  aListForm.afterInit = aListForm.afterSubmit;

  $("#gallery-pull-btn").on("click", async function () {
    const $btn = $(this);
    $btn.prop("disabled", true).text("拉取中...");
    try {
      const csrftoken = $("[name=csrfmiddlewaretoken]").val();
      await fetch(window.URLS["gallery:pull"], {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken,
          mode: "same-origin",
        },
      });
      await fetchMediaLibLinkers();
    } catch (error) {
      console.error("拉取失败:", error);
    } finally {
      $btn.prop("disabled", false).text("拉取");
    }
  });
  fetchMediaLibLinkers();
});

async function fetchAListInfo() {
  const host = $("input[name=host]").val();
  const response = await fetch(
    `${window.URLS["alist:info"]}?host=${encodeURI(host)}`,
  );
  const data = await response.json();
  if (!response.ok) {
    console.error(data);
  }

  document.getElementById("alist-avatar").src = data["avatar"];
  document.getElementById("alist-sitename").innerHTML = data["site_name"];
}

async function fetchMediaLibLinkers() {
  const resp = await fetch(window.URLS["gallery:linkers"]);
  if (!resp.ok) return;
  const data = await resp.json();
  // Last commit
  const last = data.last_commit;
  const lastCommitEl = document.getElementById("gallery-last-commit");
  if (last && lastCommitEl) {
    lastCommitEl.innerHTML = `
          <div class="mb-1 small">
            <span class='text-monospace'>${last.hash}</span>
            <span class='mx-2'>|</span>
            <span>${last.author}</span>
            <span class='mx-2'>|</span>
            <span class='text-secondary'>${last.date}</span>
          </div>
          <div class="text-muted large">${last.message}</div>
      `;
  }
  // Linkers
  const linkerList = document.getElementById("gallery-linker-list");
  if (linkerList) {
    linkerList.innerHTML = "";
    (data.linkers || []).forEach((linker) => {
      const li = document.createElement("li");
      li.className =
        "list-group-item d-flex justify-content-between align-items-center";
      li.innerHTML = `
        <span>
          <strong>${linker.name}</strong>
          <a href='${linker.url}' target='_blank' rel='noopener'>${linker.url}</a>
        </span>
        <span class='badge bg-secondary mx-2'>${linker.id}</span>
        <div class="form-check form-switch m-0">
          <input class="form-check-input gallery-linker-switch" type="checkbox" id="linker-switch-${linker.id}" data-linker-id="${linker.id}" ${linker.enabled ? "checked" : ""}>
          <label class="form-check-label" for="linker-switch-${linker.id}">${linker.enabled ? "启用" : "禁用"}</label>
        </div>
      `;
      linkerList.appendChild(li);
    });
    linkerList.querySelectorAll(".gallery-linker-switch").forEach((el) => {
      el.addEventListener("change", async function () {
        const linkerId = this.getAttribute("data-linker-id");
        const enabled = this.checked;
        const csrftoken = $(`[name=csrfmiddlewaretoken]`).val();
        await fetch(
          window.URLS["gallery:set-linker-enabled"] ||
            "/api/gallery/set-linker-enabled/",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": csrftoken,
              mode: "same-origin",
            },
            body: JSON.stringify({ linker_id: linkerId, enabled }),
          },
        );
        // 更新label
        const label = linkerList.querySelector(
          `label[for='linker-switch-${linkerId}']`,
        );
        if (label) label.textContent = enabled ? "启用" : "禁用";
      });
    });
  }
}
