let revenueChart = null;

document.addEventListener("DOMContentLoaded", function () {

  const body = document.body;
  const sidebar = document.querySelector(".sidebar");
  const app = document.querySelector(".app");

  // === Matikan semua transition di seluruh layout ===
  body.classList.add("no-transition");

  // === Restore collapsed state ===
  const collapsed = localStorage.getItem("sidebar-collapsed");
  if (collapsed === "true") {
      sidebar.classList.add("collapsed");
      app.classList.add("sidebar-collapsed");
  }

  // === Re-enable transition setelah layout sudah pas ===
  setTimeout(() => {
      body.classList.remove("no-transition");
  }, 120);

    // Ambil data dari Jinja yang sudah di-inject ke window

  const ctx = document.getElementById("revenueChart");
  if (ctx) {
      revenueChart = new Chart(ctx.getContext("2d"), {
          type: "bar",
          data: {
              labels: window.dashboardData?.months || [],
              datasets: [{
                  label: "Revenue",
                  data: window.dashboardData?.revenue || [],
                  borderRadius: 10,
                  backgroundColor: "#E50D25"
              }]
          },
          options: {
              responsive: true,
              maintainAspectRatio: false,   // 🔥 penting biar resize sesuai container
              plugins: { legend: { display: false }},
              scales: {
                  y: { ticks: { color: "#ccc" } },
                  x: { ticks: { color: "#ccc" } }
              }
          }
      });
  }

  // === NEW FORM TOGGLE ===
  const btnNew = document.getElementById('btnNew');
  const newForm = document.getElementById('newForm');
  if (btnNew && newForm) {
    btnNew.addEventListener('click', () => newForm.classList.toggle('hidden'));
  }

  // === LOGIN FORM ===
  const loginForm = document.getElementById('loginForm');
  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const data = new FormData(loginForm);
      const res = await fetch('/login', {
        method: 'POST',
        body: data,
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });
      const json = await res.json();
      if (json.ok) {
        window.location = json.next || '/dashboard';
      } else {
        document.getElementById('loginMsg').innerText = json.error;
      }
    });
  }

  // === LIVE FILTER (halaman produk) ===
  const search = document.getElementById('search');
  if (search) {
    search.addEventListener('input', async (e) => {
      const q = e.target.value.toLowerCase();
      try {
        await fetch('/api/products');
        document.querySelectorAll('table tbody tr').forEach(row => {
          row.style.display = row.innerText.toLowerCase().includes(q) ? '' : 'none';
        });
      } catch (err) {}
    });
  }

  // === GLOBAL SEARCH (Enter → redirect ke /products) ===
  if (search) {
    search.addEventListener('keydown', (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        const q = search.value.trim();
        if (q.length > 0) {
          window.location.href = `/products?search=${encodeURIComponent(q)}`;
        }
      }
    });
  }

  // === SIDEBAR TOGGLE (FINAL) ===
  const toggleBtn = document.getElementById("toggleSidebar");

  if (sidebar && toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      sidebar.classList.toggle("collapsed");
      document.querySelector(".app").classList.toggle("sidebar-collapsed");

      // === Simpan ke localStorage ===
      const isCollapsed = sidebar.classList.contains("collapsed");
      localStorage.setItem("sidebar-collapsed", isCollapsed);

      // trigger chart resize (punyamu yg lama)
      setTimeout(() => {
        if (revenueChart) {
          revenueChart.resize();
          revenueChart.update();
        }
      }, 300);
    });
  }


  // === SLIDING PANEL (Kelola Produk) ===
const panel = document.getElementById("sidePanel");
const overlay = document.getElementById("overlay");
const closePanelBtn = document.getElementById("closePanelBtn");

window.openPanel = function (id) {
  if (!panel || !overlay) return;

  panel.classList.remove("hidden");   // tampilkan panel dulu
  overlay.classList.remove("hidden"); // tampilkan overlay

  // delay sedikit supaya transisi CSS bisa jalan
  setTimeout(() => {
    panel.classList.add("show");      // trigger transisi masuk
  }, 10);

  fetch(`/product/${id}/edit`)
    .then(res => res.text())
    .then(html => {
      document.getElementById("panelContent").innerHTML = html;
    });
};

function closePanel() {
  panel.classList.remove("show"); // trigger transisi keluar
  overlay.classList.add("hidden");

  // setelah transisi selesai, sembunyikan sepenuhnya
  setTimeout(() => panel.classList.add("hidden"), 350); // sama dengan durasi transition
}


if (overlay) overlay.addEventListener("click", closePanel);
if (closePanelBtn) closePanelBtn.addEventListener("click", closePanel);

// === SLIDING PANEL (Kelola Staff) ===
const staffPanel = document.getElementById("staffPanel");

window.openStaffPanel = function (id) {
  staffPanel.classList.remove("hidden");
  overlay.classList.remove("hidden");

  // Hilangkan listener panel produk
  overlay.onclick = closeStaffPanel;

  setTimeout(() => {
    staffPanel.classList.add("show");
  }, 10);

  fetch(`/staff/${id}/edit`)
    .then(res => res.text())
    .then(html => {
      document.getElementById("staffPanelContent").innerHTML = html;
    });
};

function closeStaffPanel() {
  staffPanel.classList.remove("show");
  overlay.classList.add("hidden");

  setTimeout(() => {
    staffPanel.classList.add("hidden");
  }, 350);
}

if (overlay) overlay.addEventListener("click", closeStaffPanel);
if (closePanelBtn) closePanelBtn.addEventListener("click", closeStaffPanel);

window.openModal = function (card) {
    document.getElementById("modalName").innerText = card.dataset.name;
    document.getElementById("modalCategory").innerText = "Kategori: " + card.dataset.category;

    let price = parseInt(card.dataset.price).toLocaleString('id-ID');
    document.getElementById("modalPrice").innerText = "Rp " + price;

    const desc = card.dataset.description;

    document.getElementById("modalDesc").textContent =
        desc && desc.trim()
            ? desc
            : "Tidak ada deskripsi";

    document.getElementById("modalImg").src = card.dataset.img || "";

    document.getElementById("modalWa").href =
        "https://wa.me/628972342612?text=Halo%20saya%20mau%20beli%20" +
        encodeURIComponent(card.dataset.name);

    document.getElementById("productModal").style.display = "flex";
};

const modal = document.getElementById("productModal");
const closeBtn = document.querySelector(".close-btn");

if (closeBtn) {
    closeBtn.addEventListener("click", () => {
        modal.style.display = "none";
    });
}

window.addEventListener("click", (e) => {
    if (e.target === modal) {
        modal.style.display = "none";
    }
});

initCarousel();

  // Load all lucide icons
  lucide.createIcons();
});

// === SLIDESHOW ===
let slideIndex = 0;
let autoSlideTimer;

function initCarousel() {
    const slides = document.getElementsByClassName("carousel-slide");
    if (slides.length === 0) return;  // aman dan tidak mematikan script lain

    generateDots();
    showSlide(slideIndex);
    startAutoSlide();
}

function generateDots() {
    const dotsContainer = document.getElementById("carouselDots");
    const slides = document.getElementsByClassName("carousel-slide");

    dotsContainer.innerHTML = ""; // bersihkan

    for (let i = 0; i < slides.length; i++) {
        const dot = document.createElement("span");
        dot.classList.add("carousel-dot");
        dot.setAttribute("data-index", i);

        dot.addEventListener("click", () => {
            slideIndex = i;
            showSlide(slideIndex);
            resetAutoSlide();
        });

        dotsContainer.appendChild(dot);
    }
}

function startAutoSlide() {
    autoSlideTimer = setInterval(() => {
        nextSlide();
    }, 3500);
}

function resetAutoSlide() {
    clearInterval(autoSlideTimer);
    startAutoSlide();
}

function nextSlide() {
    changeSlide(1);
}

function prevSlide() {
    changeSlide(-1);
}

function manualSlide(n) {
    changeSlide(n);
    resetAutoSlide();
}

function changeSlide(n) {
    const slides = document.getElementsByClassName("carousel-slide");
    slideIndex += n;

    if (slideIndex >= slides.length) slideIndex = 0;
    if (slideIndex < 0) slideIndex = slides.length - 1;

    showSlide(slideIndex);
}

function showSlide(index) {
    const slides = document.getElementsByClassName("carousel-slide");
    const dots = document.getElementsByClassName("carousel-dot");

    for (let i = 0; i < slides.length; i++) {
        slides[i].style.display = "none";
        if (dots[i]) dots[i].classList.remove("active");
    }

    slides[index].style.display = "block";
    if (dots[index]) dots[index].classList.add("active");
}