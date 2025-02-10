$(document).ready(function () {
  window.dismissGroup = function () {
    // Dismiss channel
    fetch(window.URLS["channel:detail"], {
      method: "DELETE",
      headers: {
        "X-CSRFToken": document.querySelector("input[name=csrfmiddlewaretoken]")
          .value,
      },
    }).then((response) => {
      if (response.ok) {
        window.location.href = window.URLS["view:channels"];
      } else {
        response.json().then((data) => {
          showAlert(data.detail, "danger");
        });
        bootstrap.Modal.getInstance("#confirm-dismiss-model").hide();
      }
    });
  };

  // Bilibili
  bindBiliModalEvent();
  window.onBiliRefreshClicked = () => fetchAListInfo(true);

  const biliForm = $("#bili-form")[0];
  biliForm.afterSubmit = async function (response) {
    if (response.ok) {
      fetchBilibiliInfo();
    } else if (response.status === 404) {
      window.clearAlert();

      const data = $("#bili-form").serializeObject();
      response = await fetch(window.URLS["bili-account:list"], {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": data["csrfmiddlewaretoken"],
          mode: "same-origin",
        },
        body: JSON.stringify(data),
      });
      biliForm.showResult(response);

      if (response.ok) {
        fetchBilibiliInfo();
      }
    }
  };
  biliForm.afterInit = fetchBilibiliInfo;

  // AList
  window.onAlistRefreshClicked = () => fetchAListInfo();

  const aListForm = $("#alist-form")[0];
  aListForm.afterSubmit = async function (response) {
    if (response.ok) {
      fetchAListInfo();
    } else if (response.status === 404) {
      window.clearAlert();

      const data = $("#alist-form").serializeObject();
      response = await fetch(window.URLS["alist-account:list"], {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": data["csrfmiddlewaretoken"],
          mode: "same-origin",
        },
        body: JSON.stringify(data),
      });
      biliForm.showResult(response);

      if (response.ok) {
        fetchAListInfo();
      }
    }
  };
  aListForm.afterInit = fetchAListInfo;
});

function bindBiliModalEvent() {
  const qrModel = document.getElementById("qrModal");
  qrModel.addEventListener("shown.bs.modal", async () => {
    await generateQrCode();
    startPulling();
  });
  qrModel.addEventListener("hidden.bs.modal", () => {
    stopPulling();
    clearCanvas();
  });
}

let qrcodeKey, pullTimer;

async function generateQrCode() {
  const title = document.getElementById("qrModalLabel");
  title.innerHTML = "正在加载……";

  const response = await fetch(window.URLS["bili:qr"]);
  if (!response.ok) {
    throw new Error(`Response status: ${response.status}`);
  }

  const json = await response.json();
  QRCode.toCanvas(document.getElementById("canvas"), json["url"]);

  qrcodeKey = json["qrcode_key"];
}

function startPulling() {
  const title = document.getElementById("qrModalLabel");
  title.innerHTML = "使用 Bilibili App 扫描下方二维码";

  pullTimer = setInterval(async () => {
    const response = await fetch(
      `${window.URLS["bili:pull"]}?key=${qrcodeKey}`
    );
    if (!response.ok) {
      throw new Error(`Response status: ${response.status}`);
    }

    const json = await response.json();
    switch (json["code"]) {
      case 86101:
        console.info("wait for scan");
        break;
      case 86090:
        console.info("wait for confirm");
        title.innerHTML = "请在 App 中确认登录";
        break;
      case 86038:
        console.info("qr outdated!");
        title.innerHTML = "二维码已过期！请重新生成";
        stopPulling();
        break;
      case 0:
        console.info("success!");
        stopPulling();
        submitValue(json);
        break;
      default:
        console.warn(`unknown code: ${json["status"]}`);
    }
  }, 2000);
}

function stopPulling() {
  clearInterval(pullTimer);
}

function clearCanvas() {
  const canvas = document.getElementById("canvas");
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, canvas.width, canvas.height);
}

async function submitValue(data) {
  const qrModel = bootstrap.Modal.getInstance("#qrModal");
  await qrModel.hide();

  const form = $("#bili-form")[0];
  form.loadData(data);
  form.execSubmit();
}

async function fetchBilibiliInfo(force = false) {
  console.log(123123123);
  const sess = $("input[name=sess]").val();
  const response = await fetch(
    `${window.URLS["bili:info"]}?sess=${sess}${force ? "&force" : ""}`
  );
  if (!response.ok) {
    console.warn("cannot load bilibili user info:");
    console.log(response);
  }

  const json = await response.json();
  document.getElementById("bili-avatar").src = json["avatar"];
  document.getElementById("bili-username").innerHTML = json["username"];
  document.getElementById("bili-vip").innerHTML = `大会员：${
    json["vip"] ? "是" : "否"
  }`;
}

async function fetchAListInfo() {
  const url = window.URLS["alist:user-info"];
  const username = $("#alist-form input[name='username']").val();
  const password = $("#alist-form input[name='password']").val();

  const response = await fetch(
    `${url}?username=${username}&password=${password}`
  );
  const data = await response.json();

  let permissionContent = "";
  if (!response.ok) {
    console.error(data);
    permissionContent = `<span class="badge text-bg-danger mx-1">无法登录</span>`;
  } else {
    $("#alist-base-path").html(data["base_path"]);

    const permission = data["permission"];
    if (permission === "admin") {
      permissionContent = '<span class="badge text-bg-success">管理员</span>';
    } else {
      const permissions = [
        { mask: 0b0000001000, title: "创建目录或上传" },
        { mask: 0b0100000000, title: "Webdav 读取" },
      ];
      for (const item of permissions) {
        if ((item.mask & permission) > 0) {
          permissionContent += `<span class="badge text-bg-success mx-1">${item.title}</span>`;
        } else {
          permissionContent += `<span class="badge text-bg-danger mx-1">${item.title}：缺少权限</span>`;
        }
      }
    }
  }
  $("#alist-permissions").html(permissionContent);
}
