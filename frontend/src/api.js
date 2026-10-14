const API_BASE = import.meta.env.VITE_API_URL || "";

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function listFiles() {
  return handle(await fetch(`${API_BASE}/api/files`));
}

export async function uploadFile(file, fileId = null, onProgress) {
  const form = new FormData();
  form.append("file", file);
  if (fileId) form.append("file_id", fileId);

  // Fetch has no upload progress; use XHR when callback provided
  if (!onProgress) {
    return handle(
      await fetch(`${API_BASE}/api/files/upload`, {
        method: "POST",
        body: form,
      })
    );
  }

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/files/upload`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      try {
        const data = JSON.parse(xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300) resolve(data);
        else reject(new Error(data.detail || xhr.statusText));
      } catch {
        reject(new Error(xhr.statusText));
      }
    };
    xhr.onerror = () => reject(new Error("Upload failed"));
    xhr.send(form);
  });
}

export async function getFileStats(fileId) {
  return handle(await fetch(`${API_BASE}/api/files/${fileId}/stats`));
}

export async function deleteFile(fileId) {
  return handle(
    await fetch(`${API_BASE}/api/files/${fileId}`, { method: "DELETE" })
  );
}

export async function deleteVersion(fileId, version) {
  return handle(
    await fetch(`${API_BASE}/api/files/${fileId}/versions/${version}`, {
      method: "DELETE",
    })
  );
}

export async function getChunkReport(fileId, version) {
  const q = version != null ? `?version=${version}` : "";
  return handle(await fetch(`${API_BASE}/api/files/${fileId}/chunks${q}`));
}

export async function getGlobalStats() {
  return handle(await fetch(`${API_BASE}/api/files/stats/global`));
}

export function downloadUrl(fileId, version) {
  const q = version != null ? `?version=${version}` : "";
  return `${API_BASE}/api/files/${fileId}/download${q}`;
}

export function formatBytes(n) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  let bytes = Number(n);
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024;
    i += 1;
  }
  const whole = Math.abs(bytes - Math.round(bytes)) < 0.05;
  const digits = i === 0 || bytes >= 10 || whole ? 0 : 1;
  return `${bytes.toFixed(digits)} ${units[i]}`;
}

export function formatTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
