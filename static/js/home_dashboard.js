// ======================
//  Calendário Ultra-Compacto
// ======================

(function () {

    function formatMonthName(d) {
        return d.toLocaleString('pt-BR', { month: 'long', year: 'numeric' });
    }

    function sameDate(a, b) {
        return a.getFullYear() === b.getFullYear() &&
               a.getMonth() === b.getMonth() &&
               a.getDate() === b.getDate();
    }

    function renderMiniCompactCalendar(container, year, month, eventDates) {
        container.innerHTML = '';

        const header = document.createElement('div');
        header.className = 'mc-header';

        const prevBtn = document.createElement('button');
        prevBtn.type = 'button';
        prevBtn.className = 'btn btn-sm';
        prevBtn.style.padding = '2px 6px';
        prevBtn.innerText = '‹';

        const nextBtn = prevBtn.cloneNode(true);
        nextBtn.innerText = '›';

        const title = document.createElement('div');
        title.style.flex = '1';
        title.style.textAlign = 'center';
        title.innerText = formatMonthName(new Date(year, month, 1));

        header.appendChild(prevBtn);
        header.appendChild(title);
        header.appendChild(nextBtn);
        container.appendChild(header);

        const weekdays = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
        const grid = document.createElement('div');
        grid.className = 'mc-grid';

        weekdays.forEach(wd => {
            const w = document.createElement('div');
            w.className = 'mc-weekday';
            w.innerText = wd;
            grid.appendChild(w);
        });

        const firstDay = new Date(year, month, 1).getDay();
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const today = new Date();

        for (let i = 0; i < firstDay; i++) {
            const emptyCell = document.createElement('div');
            emptyCell.className = 'mc-day empty';
            grid.appendChild(emptyCell);
        }

        for (let d = 1; d <= daysInMonth; d++) {
            const cell = document.createElement('div');
            cell.className = 'mc-day';

            const date = new Date(year, month, d);
            const num = document.createElement('div');
            num.className = 'mc-num';
            num.innerText = d;

            if (sameDate(date, today)) cell.classList.add('today');

            const hasEvent = eventDates.some(ed => sameDate(new Date(ed), date));
            if (hasEvent) {
                const dot = document.createElement('div');
                dot.className = 'mc-dot';
                cell.appendChild(dot);
            }

            cell.appendChild(num);
            grid.appendChild(cell);
        }

        container.appendChild(grid);

        prevBtn.addEventListener('click', () => {
            const newDate = new Date(year, month - 1, 1);
            fetchEventsAndRender(container, newDate.getFullYear(), newDate.getMonth());
        });

        nextBtn.addEventListener('click', () => {
            const newDate = new Date(year, month + 1, 1);
            fetchEventsAndRender(container, newDate.getFullYear(), newDate.getMonth());
        });
    }

    function fetchEventsAndRender(container, year, month) {
        fetch('/entregas-datas')
            .then(res => res.json())
            .then(events => {
                const eventDates = (events || []).map(e => e.start);
                renderMiniCompactCalendar(container, year, month, eventDates);
            })
            .catch(err => {
                console.error('Erro ao buscar eventos', err);
                renderMiniCompactCalendar(container, year, month, []);
            });
    }

    document.addEventListener("DOMContentLoaded", function () {
        const el = document.getElementById('miniCompactCalendario');
        if (el) {
            const now = new Date();
            fetchEventsAndRender(el, now.getFullYear(), now.getMonth());
        }
    });

})();

// ======================
//  MINI MAPA LEAFLET
// ======================

document.addEventListener("DOMContentLoaded", function () {

    const mapaEl = document.getElementById('miniMapa');

    if (mapaEl && typeof L !== 'undefined') {

        const map = L.map('miniMapa').setView([-27.358885, -53.398043], 12); //Coordenadas iniciais(Meio de FW)

        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19
        }).addTo(map);

        fetch('/entregas-pendentes')
            .then(res => res.json())
            .then(marcadores => {
                const bounds = [];

                marcadores.forEach(m => {
                    if (!m.lat || !m.lng) return;

                    const marker = L.marker([m.lat, m.lng]).addTo(map);
                    marker.bindPopup(m.n_nota ? `Pedido ${m.n_nota}` : 'Entrega pendente');

                    bounds.push([m.lat, m.lng]);
                });

                if (bounds.length > 0) {
                    map.fitBounds(bounds, { padding: [30, 30] });
                }
            });
    }
});

// ======================
//  MAPA EXPANDIDO (BOTÃO)
// ======================

document.addEventListener("DOMContentLoaded", function () {

    const btnAbrir = document.getElementById("abrirMapaExpandidoBtn");
    const overlay = document.getElementById("overlayMapa");
    const fechar = document.getElementById("fecharOverlayMapa");

    if (!btnAbrir || !overlay || !fechar) {
        console.error("Elemento do mapa expandido não encontrado.");
        return;
    }

    let mapaExpandido = null;

    btnAbrir.addEventListener("click", () => {

        overlay.style.display = "flex";

        setTimeout(() => {

            if (!mapaExpandido) {

                mapaExpandido = L.map("mapaExpandido").setView([-27.358885, -53.398043], 12);

                L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
                    maxZoom: 19
                }).addTo(mapaExpandido);

                fetch("/entregas-pendentes")
                    .then(res => res.json())
                    .then(marcadores => {
                        const bounds = [];

                        marcadores.forEach(m => {
                            if (!m.lat || !m.lng) return;

                            const marker = L.marker([m.lat, m.lng]).addTo(mapaExpandido);
                            marker.bindPopup(m.n_nota ? `Pedido ${m.n_nota}` : "Entrega pendente");
                            bounds.push([m.lat, m.lng]);
                        });

                        if (bounds.length > 0) {
                            mapaExpandido.fitBounds(bounds, { padding: [30, 30] });
                        }
                    });

            } else {
                mapaExpandido.invalidateSize();
            }

        }, 200);
    });

    fechar.addEventListener("click", () => {
        overlay.style.display = "none";
    });
});
