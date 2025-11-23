document.addEventListener("DOMContentLoaded", function () {

    // ---------- FullCalendar: eventos (entregas) ----------
    const calendarioEl = document.getElementById('calendario');
    if (calendarioEl && typeof FullCalendar !== 'undefined') {
        fetch('/entregas-datas')
            .then(res => res.json())
            .then(eventos => {
                const calendar = new FullCalendar.Calendar(calendarioEl, {
                    initialView: 'dayGridMonth',
                    locale: 'pt-br',
                    events: eventos,
                    height: 'auto'
                });
                calendar.render();
            }).catch(err => {
                console.error('Erro ao buscar eventos do calendário', err);
            });
    }

    // ---------- Leaflet: mapa de entregas pendentes ----------
    const mapaEl = document.getElementById('miniMapa');
    if (mapaEl && typeof L !== 'undefined') {
        // Ponto inicial: tenta centralizar por Brasil (fallback)
        const map = L.map('miniMapa').setView([-29.7, -53.7], 12);

        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19
        }).addTo(map);

        fetch('/entregas-pendentes')
            .then(res => res.json())
            .then(marcadores => {
                if (!marcadores || marcadores.length === 0) return;

                const bounds = [];
                marcadores.forEach(m => {
                    if (!m.lat || !m.lng) return;
                    const marker = L.marker([m.lat, m.lng]).addTo(map);
                    const titulo = m.n_nota ? `Pedido ${m.n_nota}` : 'Entrega pendente';
                    marker.bindPopup(titulo);
                    bounds.push([m.lat, m.lng]);
                });

                if (bounds.length > 0) {
                    map.fitBounds(bounds, { padding: [30, 30] });
                }
            }).catch(err => {
                console.error('Erro ao buscar marcadores', err);
            });
    }
});
