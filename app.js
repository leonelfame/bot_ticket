const events = [
  ["TIZY 3RD WORLD TOUR", "จำหน่ายบัตร", "variant-1"],
  ["natori ONE-MAN LIVE", "เปิดจำหน่าย", "variant-2"],
  ["YG WORLD TOUR: THE C...", "เปิดจำหน่าย", "variant-3"],
  ["Bush Blossom Fan Fes...", "เปิดจำหน่าย", "variant-4"],
  ["2026 KISS OF LIFE ASI...", "เปิดจำหน่าย", "variant-2"],
  ["LANY: soft world tour...", "เปิดจำหน่าย", "variant-3"],
  ["BRIGHT HORIZON", "เปิดจำหน่าย", "variant-4"],
  ["LOVE OUT LOUD FAN FES...", "เปิดจำหน่าย", "variant-1"],
  ["CAMERATA RCO", "เปิดจำหน่าย", "variant-4"],
  ["JEANIEVVE THE CRYS...", "เปิดจำหน่าย", "variant-2"],
  ["Laufey: A Matter of T...", "เปิดจำหน่าย", "variant-1"],
  ["GOTCHA POP 4 CONCERT", "เปิดจำหน่าย", "variant-3"]
];

const zones = [
  { label: "A1", available: 18, price: 8169 },
  { label: "B1", available: 12, price: 7200 },
  { label: "C2", available: 8, price: 6500 },
  { label: "D1", available: 6, price: 5900 }
];

const eventGrid = document.querySelector("#eventGrid");
const seatRows = document.querySelector("#seatRows");
const taskList = document.querySelector("#taskList");
const logList = document.querySelector("#logList");
const zoneSelect = document.querySelector("#zoneSelect");
const accessToggle = document.querySelector("#accessToggle");

let taskId = 1;
let selectedEvent = 0;

function renderEvents() {
  eventGrid.innerHTML = events
    .map((event, index) => {
      const [name, status, variant] = event;
      const active = index === selectedEvent ? " is-active" : "";
      return `
        <article class="event-card${active}" data-index="${index}">
          <div class="poster ${variant}">${name.split(" ")[0]}</div>
          <div class="event-meta">
            <div class="event-name">${name}</div>
            <div class="event-status">${status}</div>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderSeats() {
  const rows = ["H", "I", "J", "K", "L", "M"];
  seatRows.innerHTML = rows
    .map((row, rowIndex) => {
      const count = Math.min(2 + rowIndex, 6);
      const seats = Array.from({ length: count }, (_, index) => {
        const number = String(6 - index).padStart(2, "0");
        const dim = index > 3 && rowIndex < 4 ? " dim" : "";
        return `<span class="seat${dim}">${number}</span>`;
      }).join("");
      return `<div class="seat-row"><span class="row-label">${row}</span>${seats}</div>`;
    })
    .join("");
}

function timestamp() {
  return new Date().toLocaleTimeString("th-TH", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}

function addLog(message, type = "ok") {
  const item = document.createElement("li");
  item.className = type;
  item.textContent = `[${timestamp()}] ${message}`;
  logList.appendChild(item);
  while (logList.children.length > 40) {
    logList.removeChild(logList.firstElementChild);
  }
  logList.scrollTop = logList.scrollHeight;
}

function selectedZone() {
  const option = zoneSelect.value.match(/^([A-Z]\d)/);
  return option ? option[1] : "A1";
}

function createTask() {
  if (taskList.querySelector(".empty-state")) {
    taskList.innerHTML = "";
  }

  const zone = selectedZone();
  const qty = document.querySelector("#qtyInput").value || "1";
  const delay = document.querySelector("#delayInput").value || "1000";
  const id = String(taskId++).padStart(2, "0");

  const card = document.createElement("article");
  card.className = "task-card";
  card.innerHTML = `
    <div class="task-head">
      <span>Task #${id}</span>
      <span class="task-pill">READY</span>
    </div>
    <div class="task-detail">
      Event: ${events[selectedEvent][0]}<br />
      Zone: ${zone} | Qty: ${qty} | Delay: ${delay}ms<br />
      Mode: local test, no external requests
    </div>
    <div class="progress"><span></span></div>
  `;
  taskList.prepend(card);
  addLog(`สร้างงานจำลอง #${id} | zone ${zone} | qty ${qty}`);

  const progress = card.querySelector(".progress span");
  const pill = card.querySelector(".task-pill");
  let pct = 0;
  const timer = setInterval(() => {
    pct += Math.floor(Math.random() * 18) + 10;
    progress.style.width = `${Math.min(pct, 100)}%`;

    if (pct >= 45 && pct < 85) {
      pill.textContent = "PULLING";
      addLog(`Task #${id} ตรวจที่นั่งจำลองใน ${zone}`, "warn");
    }

    if (pct >= 100) {
      clearInterval(timer);
      pill.textContent = "PAYMENT";
      addLog(`Task #${id} ได้คิวชำระเงินจำลองแล้ว`, "ok");
    }
  }, 850);
}

function refreshZones() {
  zones.forEach((zone) => {
    zone.available = Math.max(2, zone.available + Math.floor(Math.random() * 7) - 3);
  });

  zoneSelect.innerHTML = zones
    .map((zone) => `<option>${zone.label} (ว่าง ${zone.available})</option>`)
    .join("");

  addLog("อัปเดตโซนจำลองสำเร็จ");
}

eventGrid.addEventListener("click", (event) => {
  const card = event.target.closest(".event-card");
  if (!card) return;
  selectedEvent = Number(card.dataset.index);
  renderEvents();
  document.querySelector("#eventUrl").value =
    `https://www.thaiticketmajor.com/concert/${events[selectedEvent][0].toLowerCase().replaceAll(" ", "-")}.html`;
  addLog(`เลือกอีเวนต์: ${events[selectedEvent][0]}`);
});

document.querySelector("#createTask").addEventListener("click", createTask);
document.querySelector("#emptyCreate").addEventListener("click", createTask);
document.querySelector("#fetchZones").addEventListener("click", refreshZones);
document.querySelector("#loadDates").addEventListener("click", refreshZones);
document.querySelector("#startQueue").addEventListener("click", () => {
  addLog("เริ่มคิวจำลอง: ตรวจโซนและที่นั่งแบบ local", "warn");
  createTask();
});
document.querySelector("#openPayment").addEventListener("click", () => {
  addLog("เปิดหน้าชำระเงินจำลองใน task panel", "ok");
});
document.querySelector("#openCart").addEventListener("click", () => {
  addLog("เปิดตะกร้าจำลอง", "warn");
});
document.querySelector("#addAccount").addEventListener("click", () => {
  addLog("เพิ่มบัญชีจำลองแล้ว 1 รายการ");
});
document.querySelector("#openTask").addEventListener("click", () => {
  addLog("Task Manager พร้อมทำงาน");
});

accessToggle.addEventListener("click", () => {
  const enabled = accessToggle.classList.toggle("on");
  accessToggle.textContent = enabled ? "Accs: ON" : "Accs: OFF";
  addLog(enabled ? "เปิดบัญชีจำลอง" : "ปิดบัญชีจำลอง", enabled ? "ok" : "warn");
});

renderEvents();
renderSeats();
addLog("ระบบทดสอบพร้อมใช้งาน");
addLog("ไม่มีการเรียก API จริงหรือเปิดระบบจ่ายเงินจริง", "warn");
