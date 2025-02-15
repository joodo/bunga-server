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
});

async function fetchAListInfo() {
  const host = $("input[name=host]").val();
  const response = await fetch(
    `${window.URLS["alist:info"]}?host=${encodeURI(host)}`
  );
  const data = await response.json();
  if (!response.ok) {
    console.error(data);
  }

  document.getElementById("alist-avatar").src = data["avatar"];
  document.getElementById("alist-sitename").innerHTML = data["site_name"];
}
