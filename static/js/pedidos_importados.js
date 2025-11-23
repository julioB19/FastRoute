document.addEventListener('DOMContentLoaded', function() {
    // Pequena UX: confirmar antes de abrir detalhe (opcional)
    document.querySelectorAll('a.btn-outline-primary').forEach(a => {
        a.addEventListener('click', (e) => {
            // não bloquear a navegação, apenas efeito no futuro
        });
    });
});
