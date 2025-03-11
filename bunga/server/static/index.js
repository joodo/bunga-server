$(document).ready(function () {
  setDownloadButton();
});

function copyToClipboard() {
  const input = document.querySelector(".form-control");
  input.select();
  input.setSelectionRange(0, 99999); // For mobile devices
  navigator.clipboard.writeText(input.value);
}

function setDownloadButton() {
  fetch("https://gitee.com/api/v5/repos/joodo2/bunga_player/releases/latest")
    .then((response) => response.json())
    .then((response) => {
      console.log(response);
      const tagName = response["tag_name"];

      const assets = response["assets"];
      const os = getOS();

      let asset = null;
      switch (os) {
        case "macOS":
          asset = assets.find((e) => e["name"].endsWith(".dmg"));
          break;
        case "Windows":
          asset = assets.find((e) => e["name"].endsWith(".exe"));
          break;
        case "Android":
          asset = assets.find((e) => e["name"].endsWith(".arm64-v8a.apk"));
          break;
      }

      if (asset) {
        $("#download-link").html(`立即下载 v${tagName} for ${os}`);
        $("#download-link").attr("href", asset["browser_download_url"]);
        $("#other-download-link").removeClass("d-none");
      }
    });
}

function getOS() {
  if (navigator.userAgent.indexOf("Win") != -1) return "Windows";
  if (navigator.userAgent.indexOf("like Mac") != -1) return "iOS";
  if (navigator.userAgent.indexOf("Mac") != -1) return "macOS";
  if (navigator.userAgent.indexOf("Linux") != -1) return "Linux";
  if (navigator.userAgent.indexOf("Android") != -1) return "Android";
  return "unknown";
}
