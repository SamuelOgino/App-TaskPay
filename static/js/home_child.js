document.addEventListener('DOMContentLoaded', () => {
    const toasts = document.querySelectorAll('.toast-notification');
    
    toasts.forEach(toast => {
        // Espera 8 segundos (8000ms)
        setTimeout(() => {
            // Adiciona a classe que inicia a animação de saída (definida no CSS)
            toast.classList.add('hiding');
            
            // Espera a animação terminar e remove o elemento do HTML
            toast.addEventListener('animationend', () => {
                toast.remove();
                
                // Se não houver mais toasts, remove o container também para liberar cliques
                const container = document.getElementById('toast-container');
                if (container && container.children.length === 0) {
                    container.remove();
                }
            });
        }, 5000);
    });
});