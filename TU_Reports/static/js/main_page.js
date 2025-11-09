document.addEventListener('DOMContentLoaded', function () {

  // ====== สร้างแผนที่ ======
  const map = L.map('map').setView([14.0708, 100.6057], 15);

  // Layer พื้นหลัง
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);

  // ====== ดึงข้อมูล Tickets ======
  const raw = {{ tickets_geojson|safe }};
  const ticketsData = Array.isArray(raw) ? raw : (raw && raw.features ? raw.features : []);

  // ====== ฟังก์ชันสี Marker ======
  function getMarkerColor(status) {
    switch (status) {
      case 'PENDING': return '#EAB308';
      case 'IN_PROGRESS':
      case 'INSPECTING':
      case 'WORKING': return '#3B82F6';
      case 'COMPLETED':
      case 'CLOSED': return '#10B981';
      default: return '#6B7280';
    }
  }

  // ====== Marker และ Heatmap ======
  const markers = [];
  const heatPoints = [];
  const categoryHeatMaps = {};

  ticketsData.forEach(feature => {
    const props = feature.properties;
    if (!feature.geometry || !feature.geometry.coordinates) return;

    const coords = [feature.geometry.coordinates[1], feature.geometry.coordinates[0]];

    // เก็บพิกัดตาม category เพื่อทำ heatmap
    if (!categoryHeatMaps[props.category_id]) categoryHeatMaps[props.category_id] = [];
    categoryHeatMaps[props.category_id].push(coords);

    // สร้าง marker
    const marker = L.circleMarker(coords, {
      radius: props.urgency === 'CRITICAL' ? 10 : 8,
      fillColor: getMarkerColor(props.status),
      color: props.urgency === 'CRITICAL' ? '#DC2626' : '#fff',
      weight: 2,
      opacity: 1,
      fillOpacity: 0.85
    });

    // popup ข้อมูล
    marker.bindPopup(`
      <div class="popup">
        <h3>Ticket #${props.id}</h3>
        <p class="t">${props.title}</p>
        <p class="s">หมวดหมู่: ${props.category}</p>
        <p class="s">สถานะ: ${props.status_display}</p>
        <button onclick="showTicketDetails(${props.id})" class="pill-btn pill-btn--blue mt-2">ดูรายละเอียด</button>
      </div>
    `);

    marker.on('click', () => showTicketDetails(props.id));
    marker.addTo(map);
    markers.push(marker);
  });

  // ====== คำนวณความหนาแน่นสำหรับ heatmap ======
  ticketsData.forEach(feature => {
    if (!feature.geometry || !feature.geometry.coordinates) return;
    const coords = [feature.geometry.coordinates[1], feature.geometry.coordinates[0]];
    const list = categoryHeatMaps[feature.properties.category_id] || [];
    let nearby = 0, threshold = 0.001;
    list.forEach(c => {
      const d = Math.hypot(coords[0] - c[0], coords[1] - c[1]);
      if (d < threshold) nearby++;
    });
    const intensity = Math.min(nearby * 0.5, 5.0);
    heatPoints.push([...coords, intensity]);
  });

  // ====== สร้าง Heatmap Layer ======
  const heatLayer = L.heatLayer(heatPoints, {
    radius: 30,
    blur: 20,
    maxZoom: 17,
    max: 5.0,
    gradient: {
      0.0: 'rgba(0,0,255,0)',
      0.2: 'rgba(0,255,255,0.5)',
      0.4: 'rgba(0,255,0,0.7)',
      0.6: 'rgba(255,255,0,0.8)',
      0.8: 'rgba(255,165,0,0.9)',
      1.0: 'rgba(255,0,0,1.0)'
    }
  });

  // ปุ่ม toggle Heatmap
  let heatmapVisible = false;
  const toggleBtn = document.getElementById('toggleHeatmap');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', function () {
      if (heatmapVisible) {
        map.removeLayer(heatLayer);
        this.textContent = 'แสดง Heat Map';
        this.classList.remove('pill-btn--dark');
      } else {
        map.addLayer(heatLayer);
        this.textContent = 'ซ่อน Heat Map';
        this.classList.add('pill-btn--dark');
      }
      heatmapVisible = !heatmapVisible;
    });
  }

  // ====== จัด view ให้พอดีกับ marker ทั้งหมด ======
  if (markers.length > 0) {
    const group = new L.featureGroup(markers);
    map.fitBounds(group.getBounds().pad(0.1));
  }

  // ====== ฟังก์ชันแสดงรายละเอียด Ticket ======
  window.showTicketDetails = function (ticketId) {
    const t = ticketsData.find(x => x.properties.id === ticketId);
    if (!t) return;
    const p = t.properties;

    document.getElementById('detail-title').textContent = p.title;
    document.getElementById('detail-description').textContent = p.description;
    document.getElementById('detail-category').textContent = p.category;
    document.getElementById('detail-urgency').textContent = p.urgency_display;
    document.getElementById('detail-date').textContent = p.created_at;

    const badge = document.getElementById('detail-status');
    badge.className = 'status';
    badge.textContent = p.status_display;
    if (p.status === 'PENDING') badge.classList.add('status--amber');
    else if (['IN_PROGRESS', 'INSPECTING', 'WORKING'].includes(p.status)) badge.classList.add('status--blue');
    else if (['COMPLETED', 'CLOSED'].includes(p.status)) badge.classList.add('status--green');

    const beforeWrap = document.getElementById('before-photo-container');
    const afterWrap = document.getElementById('after-photo-container');
    const noPhotos = document.getElementById('no-photos');
    let has = false;

    if (p.before_photo) {
      document.getElementById('detail-before-photo').src = p.before_photo;
      beforeWrap.classList.remove('hidden');
      has = true;
    } else beforeWrap.classList.add('hidden');

    if (p.after_photo) {
      document.getElementById('detail-after-photo').src = p.after_photo;
      afterWrap.classList.remove('hidden');
      has = true;
    } else afterWrap.classList.add('hidden');

    if (!has) noPhotos.classList.remove('hidden');
    else noPhotos.classList.add('hidden');

    const panel = document.getElementById('ticketDetailsPanel');
    panel.classList.remove('hidden');
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  // ====== ปิด panel ======
  const closeBtn = document.getElementById('closeDetailsPanel');
  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      document.getElementById('ticketDetailsPanel').classList.add('hidden');
    });
  }

});
