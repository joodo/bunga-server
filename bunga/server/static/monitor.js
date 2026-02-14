let playStateInterval = null;
let currentPlayState = {
  playing: false,
  position_seconds: 0,
};

// 存储当前的缓存和日志数据
let currentCacheData = null;
let currentLogData = null;

function updatePlayPosition() {
  const posElement = document.getElementById("play-position");
  if (posElement && currentPlayState.playing) {
    currentPlayState.position_seconds += 1;
    posElement.textContent = formatTime(currentPlayState.position_seconds);
  }
}

function startPlayStateUpdate() {
  if (playStateInterval) clearInterval(playStateInterval);
  if (currentPlayState.playing) {
    playStateInterval = setInterval(updatePlayPosition, 1000);
  }
}

function formatTime(seconds) {
  const totalSeconds = Math.floor(seconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;
  const pad = (num) => String(num).padStart(2, "0");
  return `${pad(hours)}:${pad(minutes)}:${pad(secs)}`;
}

function createRow(label, value) {
  return `<tr><td>${label}</td><td><strong>${value}</strong></td></tr>`;
}

function updateRefreshTime() {
  const now = new Date();
  const timeStr = now.toLocaleString("zh-CN");
  document.getElementById("last-refresh-time").textContent = timeStr;
}

window.downloadSnapshot = function () {
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const snapshot = {
    timestamp: new Date().toISOString(),
    cache: currentCacheData,
    logs: currentLogData,
  };

  const blob = new Blob([JSON.stringify(snapshot, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `bunga_snapshot.${timestamp}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

window.onRefresh = async function () {
  updateRefreshTime();
  onRefreshCache();
  onRefreshLogs();
};

window.onRefreshCache = async function () {
  const response = await fetch(URLS["monitor:cache"]);
  const data = await response.json();

  // 保存数据用于快照
  currentCacheData = data;

  // 状态信息
  document.getElementById("status-info-tbody").innerHTML = `
    ${createRow("频道", data.channel_id)}
    ${createRow("频道状态", data.channel_status)}
    ${createRow("观看者数", data.watcher_count)}
    ${createRow("准备就绪", data.ready_watchers.length)}
    ${createRow("缓冲中", data.buffering_watchers.length)}
    ${createRow("待处理呼叫", data.has_pending_call ? "是" : "否")}
  `;

  // 播放状态
  let playStatusHTML = "";
  if (data.play_status) {
    currentPlayState.playing = data.play_status.playing;
    currentPlayState.position_seconds = data.play_status.position_seconds;
    playStatusHTML = `
      ${createRow("播放中", data.play_status.playing ? "是" : "否")}
      ${createRow("进度", `<strong id="play-position">${formatTime(data.play_status.position_seconds)}</strong>`)}
    `;
    startPlayStateUpdate();
  }
  document.getElementById("play-status-tbody").innerHTML = playStatusHTML;

  // 当前投影
  const projTable = document.getElementById("projection-table");
  const noProjMsg = document.getElementById("no-projection");
  if (data.current_projection) {
    document.getElementById("projection-tbody").innerHTML = `
      ${createRow("记录ID", data.current_projection.record_id)}
      ${createRow("标题", data.current_projection.title)}
      ${createRow("来源", data.current_projection.source)}
      ${createRow("分享者", `${data.current_projection.sharer_name} (${data.current_projection.sharer_id})`)}
    `;
    projTable.style.display = "";
    noProjMsg.style.display = "none";
  } else {
    projTable.style.display = "none";
    noProjMsg.style.display = "";
  }

  // 观看者列表
  const watcherTable = document.getElementById("watcher-table");
  const noWatchersMsg = document.getElementById("no-watchers");
  if (data.watcher_list && data.watcher_list.length > 0) {
    let watchers = "";
    for (const w of data.watcher_list) {
      let status = "未知";
      if (data.ready_watchers.includes(w.id)) {
        status = "就绪";
      } else if (data.buffering_watchers.includes(w.id)) {
        status = "缓冲";
      }
      watchers += `
        <tr>
          <td>${w.id}</td>
          <td>${w.name}</td>
          <td><span class="watcher-color-badge" style="--color-hue: ${w.color_hue};">${w.color_hue}</span></td>
          <td><strong>${status}</strong></td>
        </tr>
      `;
    }
    document.getElementById("watcher-tbody").innerHTML = watchers;
    watcherTable.style.display = "";
    noWatchersMsg.style.display = "none";
  } else {
    watcherTable.style.display = "none";
    noWatchersMsg.style.display = "";
  }
};

window.onRefreshLogs = async function () {
  const response = await fetch(URLS["monitor:logs"]);
  const data = await response.json();

  // 保存数据用于快照
  currentLogData = data;

  const container = document.getElementById("logs-container");

  if (data.logs && data.logs.length > 0) {
    const frag = document.createDocumentFragment();
    for (const log of data.logs) {
      const d = document.createElement("div");
      d.textContent = log;
      frag.appendChild(d);
    }
    container.replaceChildren(frag);
  } else {
    const p = document.createElement("p");
    p.className = "text-muted";
    p.textContent = "暂无日志";
    container.replaceChildren(p);
  }
};

document.addEventListener("DOMContentLoaded", function () {
  onRefresh();
});

window.onResetChannel = async function () {
  const confirmed = confirm(
    "确定要重置频道状态吗？这将清除所有缓存信息、观看者列表和投影。",
  );
  if (!confirmed) {
    return;
  }

  try {
    const response = await fetch(URLS["monitor:reset"], {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken":
          document.querySelector("[name=csrfmiddlewaretoken]")?.value || "",
      },
    });

    if (response.ok) {
      const data = await response.json();
      alert("频道状态已成功重置");
      onRefresh();
    } else {
      const error = await response.json();
      alert("重置失败: " + (error.error || "未知错误"));
    }
  } catch (error) {
    console.error("Error:", error);
    alert("重置失败: " + error.message);
  }
};
