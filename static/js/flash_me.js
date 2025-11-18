// Espera o documento HTML carregar antes de rodar o script
document.addEventListener("DOMContentLoaded", () => {

    // 1. Encontra todas as mensagens flash na página (usando a classe .flash)
    const flashMessages = document.querySelectorAll(".flash");

    // 2. Para cada mensagem encontrada...
    flashMessages.forEach((message) => {

        // 3. Define um "cronômetro" para 5 segundos (5000 milissegundos)
        setTimeout(() => {
            
            // 4. Inicia o fade-out (ativando a transição do CSS)
            message.style.opacity = '0';

            // 5. Define outro "cronômetro" para remover a mensagem
            //    (0.5s depois do fade-out começar, para dar tempo da animação rodar)
            setTimeout(() => {
                message.style.display = 'none';
            }, 500); // 500ms = 0.5s (o tempo da nossa transição do CSS)

        }, 3500); // 5 segundos
    });

});