(function(){
  // ===== Map =====
  const mapEl = document.getElementById('map');
  if (!mapEl) return;

  const map = L.map(mapEl, { scrollWheelZoom: true }).setView([14.0708, 100.6057], 16);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap'
  }).addTo(map);

  // กันอาการขนาดคำนวณไม่เสร็จ
  setTimeout(() => map.invalidateSize(), 150);

  let marker;
  const gpsStatus = document.getElementById('gpsStatus');
  const latI = document.getElementById('latitude');
  const lngI = document.getElementById('longitude');

  function setBadge(type, text){
    gpsStatus.className = 'gps-badge ' + (type || '');
    gpsStatus.textContent = text;
  }

  // GPS button
  document.getElementById('getGPS').addEventListener('click', function() {
    setBadge('is-loading','กำลังค้นหาตำแหน่ง...');
    if (!navigator.geolocation) {
      setBadge('is-error','เบราว์เซอร์ไม่รองรับ GPS');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      pos => {
        const lat = pos.coords.latitude, lng = pos.coords.longitude;
        latI.value = lat; lngI.value = lng;
        if (marker) map.removeLayer(marker);
        marker = L.marker([lat, lng]).addTo(map);
        map.setView([lat, lng], 17);
        setBadge('is-ok','ใช้ตำแหน่งปัจจุบันแล้ว');
      },
      () => setBadge('is-error','ไม่สามารถเข้าถึง GPS ได้ กรุณาเลือกบนแผนที่')
    );
  });

  // Click map to set point
  map.on('click', e => {
    if (marker) map.removeLayer(marker);
    marker = L.marker(e.latlng).addTo(map);
    latI.value = e.latlng.lat; lngI.value = e.latlng.lng;
    setBadge('is-ok','เลือกตำแหน่งบนแผนที่แล้ว');
  });

  // ===== Upload: drag & drop + preview + size check =====
  const dz = document.getElementById('dropzone');
  const input = document.getElementById('before_photo');
  const preview = document.getElementById('photoPreview');

  dz.addEventListener('click', () => input.click());
  ['dragenter','dragover'].forEach(evt => dz.addEventListener(evt, e => {
    e.preventDefault(); e.stopPropagation(); dz.classList.add('is-hover');
  }));
  ['dragleave','drop'].forEach(evt => dz.addEventListener(evt, e => {
    e.preventDefault(); e.stopPropagation(); dz.classList.remove('is-hover');
  }));
  dz.addEventListener('drop', (e) => {
    input.files = e.dataTransfer.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
  });

  input.addEventListener('change', function(e) {
    const file = e.target.files[0];
    preview.innerHTML = '';
    if (!file) return;

    if (file.size > 5 * 1024 * 1024) { // 5MB
      preview.innerHTML = '<div class="err">ไฟล์ใหญ่เกิน 5MB</div>';
      input.value = '';
      return;
    }

    const reader = new FileReader();
    reader.onload = (ev) => {
      const img = document.createElement('img');
      img.src = ev.target.result;
      img.className = 'preview-img';
      preview.appendChild(img);
    };
    reader.readAsDataURL(file);
  });
})();