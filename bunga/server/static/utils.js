export async function copyToClipboard(inputId) {
  async function doCopy(text) {
    if (navigator.clipboard && window.isSecureContext) {
      console.log("inputId");
      return await navigator.clipboard
        .writeText(text)
        .then(() => true)
        .catch(() => false);
    }

    const $container = $(".modal.show .modal-content").first();
    const $temp = $("<textarea>")
      .val(text)
      .css({ position: "absolute", left: "-9999px", top: "0" })
      .appendTo($container.length ? $container : "body");

    $temp.select();

    const success = document.execCommand("copy");
    $temp.remove();

    return success;
  }

  console.log(inputId);
  const textToCopy = $(`#${inputId}`).val();
  console.log(textToCopy);
  const isOk = await doCopy(textToCopy);
  if (isOk) {
    alert("复制成功！");
  } else {
    alert("复制失败，请手动选择复制。");
  }
}
